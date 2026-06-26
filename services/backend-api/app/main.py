"""NetGuard backend-api — dashboard gateway + live prediction stream.

Serves the parts of the public API that need the Redis prediction buffer
(`/api/metrics`, `/api/live-stats`, `/ws`) plus the model-status aggregate and
the Prometheus/Loki proxies. Incident/AIOps/inject paths are edge-routed by
nginx straight to aiops-engine/collector, so they are intentionally not here.
"""

import asyncio
import contextlib
import logging
import time
from contextlib import asynccontextmanager

import psutil
from fastapi import Depends, FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .bus import PredictionBus
from .config import settings
from .manager import ConnectionManager
from .metrics import live_stats, session_stats
from .upstreams import Upstreams

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("backend-api")

_start_time = time.time()


async def _fanout_loop(bus: PredictionBus, manager: ConnectionManager) -> None:
    """Subscribe to Redis and forward every prediction to connected clients.

    Every 10th prediction also pushes a session_stats summary so late metrics
    stay fresh without the client polling.
    """
    tick = 0
    while True:
        try:
            async for prediction in bus.listen():
                await manager.broadcast({"type": "prediction", "data": prediction})
                tick += 1
                if tick % 10 == 0:
                    records = await bus.recent(settings.buffer_read_limit)
                    summary = session_stats(records)
                    await manager.broadcast({"type": "session_stats", "data": summary})
        except Exception as exc:  # reconnect on transient Redis errors
            log.warning("fan-out loop error, retrying: %s", exc)
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = PredictionBus(
        settings.redis_url, settings.redis_channel, settings.redis_buffer_key
    )
    app.state.manager = ConnectionManager()
    app.state.upstreams = Upstreams(
        settings.inference_url, settings.aiops_url, settings.prometheus_url, settings.loki_url
    )
    task = asyncio.create_task(_fanout_loop(app.state.bus, app.state.manager))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await app.state.upstreams.close()
        await app.state.bus.close()


app = FastAPI(title="NetGuard backend-api", version="1.0.0", lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )


def get_bus(request: Request) -> PredictionBus:
    return request.app.state.bus


def get_upstreams(request: Request) -> Upstreams:
    return request.app.state.upstreams


def get_manager(request: Request) -> ConnectionManager:
    return request.app.state.manager


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(bus: PredictionBus = Depends(get_bus)) -> dict:
    await bus.ping()
    return {"status": "ready"}


@app.get("/api/status")
async def status(up: Upstreams = Depends(get_upstreams)) -> dict:
    info = await up.model_info()
    return {
        "model": bool(info.get("ready")),
        "class_names": info.get("class_names", []),
        "num_classes": info.get("num_classes", 0),
        "metrics": info.get("metrics", {}),
        "feature_importance": info.get("feature_importance", []),
        "prometheus": bool(settings.prometheus_url),
        "loki": bool(settings.loki_url),
    }


@app.get("/api/metrics")
async def metrics(
    bus: PredictionBus = Depends(get_bus),
    up: Upstreams = Depends(get_upstreams),
) -> dict:
    records = await bus.recent(settings.buffer_read_limit)
    stats = session_stats(records)
    cluster = await up.cluster_summary()
    return {
        **stats,
        "node_count": cluster.get("nodes_total", 0),
        "pod_count": cluster.get("pods_total", 0),
        "nodes_ready": cluster.get("nodes_ready", 0),
        "pods_unhealthy": cluster.get("pods_unhealthy", 0),
        "cpu_usage_percent": round(psutil.cpu_percent(interval=None), 1),
        "memory_usage_percent": round(psutil.virtual_memory().percent, 1),
        "uptime_seconds": int(time.time() - _start_time),
    }


@app.get("/api/live-stats")
async def get_live_stats(bus: PredictionBus = Depends(get_bus)) -> dict:
    records = await bus.recent(settings.buffer_read_limit)
    return live_stats(records)


@app.get("/api/cluster")
async def cluster(up: Upstreams = Depends(get_upstreams)) -> dict:
    return await up.cluster_summary()


@app.get("/api/prometheus")
async def prometheus(
    query: str,
    start: str = "",
    end: str = "",
    step: str = "60",
    up: Upstreams = Depends(get_upstreams),
) -> dict:
    return await up.prometheus(query, start, end, step)


@app.get("/api/loki")
async def loki(
    query: str,
    limit: int = Query(50, ge=1, le=1000),
    since: str = "5m",
    up: Upstreams = Depends(get_upstreams),
) -> dict:
    return await up.loki(query, limit, since)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    manager: ConnectionManager = ws.app.state.manager
    await ws.accept()
    manager.add(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive; client sends nothing meaningful
    except WebSocketDisconnect:
        manager.remove(ws)
