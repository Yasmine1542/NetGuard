"""NetGuard collector — generates network flows, scores them, publishes to Redis.

Endpoints:
  GET  /healthz    liveness
  GET  /readyz     readiness (Redis reachable)
  POST /api/inject force a specific attack type through the pipeline (demo control)
"""

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from .bus import PredictionBus
from .config import settings
from .generator import TrafficGenerator
from .inference_client import InferenceClient
from .pipeline import score_and_publish

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("collector")


async def _bootstrap_generator(gen: TrafficGenerator, client: InferenceClient) -> None:
    """Fetch feature names from inference (retrying), then load real traffic.

    Falls back silently to the synthetic generator if either step fails.
    """
    for _ in range(30):
        info = await client.model_info()
        if info and info.get("feature_names"):
            gen.set_feature_names(info["feature_names"])
            loaded = await asyncio.to_thread(gen.load_real_traffic)
            log.info("real traffic loaded: %s", loaded)
            return
        await asyncio.sleep(2)
    log.warning("inference model-info unavailable; using synthetic generator")


async def _generation_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(settings.interval_seconds)
        try:
            await score_and_publish(app.state.gen, app.state.client, app.state.bus)
        except Exception as exc:  # one bad iteration must not kill the loop
            log.warning("generation iteration failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.gen = TrafficGenerator(settings.real_traffic_sample, settings.kdd_test_url)
    app.state.client = InferenceClient(settings.inference_url)
    app.state.bus = PredictionBus(
        settings.redis_url, settings.redis_channel, settings.redis_buffer_key, settings.buffer_max
    )

    asyncio.create_task(_bootstrap_generator(app.state.gen, app.state.client))
    loop_task = asyncio.create_task(_generation_loop(app))
    try:
        yield
    finally:
        loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop_task
        await app.state.client.close()
        await app.state.bus.close()


app = FastAPI(title="NetGuard Collector", version="1.0.0", lifespan=lifespan)


# Dependency accessors — overridable in tests via app.dependency_overrides.
def get_gen(request: Request) -> TrafficGenerator:
    return request.app.state.gen


def get_client(request: Request) -> InferenceClient:
    return request.app.state.client


def get_bus(request: Request) -> PredictionBus:
    return request.app.state.bus


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(bus: PredictionBus = Depends(get_bus)) -> dict:
    await bus.ping()
    return {"status": "ready"}


@app.post("/api/inject")
async def inject(
    attack_type: str = "neptune",
    gen: TrafficGenerator = Depends(get_gen),
    client: InferenceClient = Depends(get_client),
    bus: PredictionBus = Depends(get_bus),
) -> dict:
    return await score_and_publish(gen, client, bus, label=attack_type)
