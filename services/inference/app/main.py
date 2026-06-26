"""NetGuard inference service — stateless LightGBM model serving.

Endpoints:
  GET  /healthz      liveness  (process is up)
  GET  /readyz       readiness (model is loaded)
  GET  /model-info   class names, feature names, metrics, importance
  POST /predict      score one raw flow
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .config import settings
from .detector import Detector
from .schemas import ModelInfo, PredictRequest

detector = Detector(settings.model_dir)

# ── Prometheus metrics ────────────────────────────────────────────────────────
# Scraped by kube-prometheus-stack (see the ServiceMonitor) and used by the
# Argo Rollouts AnalysisTemplate to gate the inference canary.
PREDICTIONS = Counter(
    "netguard_predictions_total", "Predictions served", ["predicted_class", "is_attack"]
)
LATENCY = Histogram("netguard_inference_latency_seconds", "Inference latency (seconds)")
MODEL_LOADED = Gauge("netguard_model_loaded", "1 when the model is loaded and ready")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        detector.load()
    except FileNotFoundError:
        # Stay unready rather than crash; /readyz reports false until artifacts appear.
        pass
    yield


app = FastAPI(title="NetGuard Inference", version="1.0.0", lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    if not detector.ready:
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "ready"}


@app.get("/model-info", response_model=ModelInfo)
def model_info() -> ModelInfo:
    return ModelInfo(
        ready=detector.ready,
        class_names=detector.class_names,
        num_classes=len(detector.class_names),
        feature_names=detector.feature_names,
        metrics=detector.metrics,
        feature_importance=detector.feature_importance,
    )


@app.get("/metrics")
def metrics() -> Response:
    MODEL_LOADED.set(1 if detector.ready else 0)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/predict")
def predict(req: PredictRequest) -> dict:
    if not detector.ready:
        raise HTTPException(status_code=503, detail="model not loaded")
    start = time.perf_counter()
    result = detector.predict(req.flow)
    elapsed = time.perf_counter() - start

    LATENCY.observe(elapsed)
    PREDICTIONS.labels(result["label"], str(result["is_attack"]).lower()).inc()

    result["latency_ms"] = round(elapsed * 1000, 2)
    result["timestamp"] = time.time()
    return result
