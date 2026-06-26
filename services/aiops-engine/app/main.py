"""NetGuard aiops-engine — incident diagnosis pipeline behind a thin API.

This service owns all Kubernetes reads (exposes /cluster) and runs the agent
pipeline. Endpoints mirror the paths the frontend already calls, so nginx can
edge-route /api/aiops, /api/incidents and /ws/aiops straight here.

  GET   /healthz /readyz
  GET   /cluster                       real cluster snapshot (k8s client)
  POST  /api/aiops/analyze             manual diagnosis trigger
  POST  /api/aiops/webhook             Alertmanager receiver
  GET   /api/incidents                 list incidents
  GET   /api/incidents/{id}            full incident record
  PATCH /api/incidents/{id}/status     resolve/suppress an incident
  WS    /ws/aiops/{incident_id}        live agent-step stream ("__all__" for any)
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .aiops.db import get_incident, list_incidents, update_incident_status
from .aiops.pipeline import run_pipeline
from .aiops.tools.kubernetes import get_cluster_summary
from .config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aiops-engine")

# Active diagnosis WebSocket connections keyed by incident_id (plus "__all__").
_aiops_ws: dict[str, list[WebSocket]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.groq_api_key:
        log.warning("GROQ_API_KEY is not set — /api/aiops/analyze will fail until configured")
    yield


app = FastAPI(title="NetGuard aiops-engine", version="1.0.0", lifespan=lifespan)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )


class AnalyzeRequest(BaseModel):
    namespace: str = ""
    pod_name: str = ""
    trigger_source: str = "manual"


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    return {"status": "ready"}


@app.get("/cluster")
def cluster() -> dict:
    """Real node/pod/namespace snapshot (sync k8s client → run in threadpool)."""
    return get_cluster_summary()


async def _broadcast_step(step: str, status: str, data: dict) -> None:
    """Push one agent step to the relevant incident's WS subscribers + '__all__'."""
    message = {"type": "aiops_step", "step": step, "status": status, "data": data}
    incident_id = data.get("incident_id", "")
    targets = _aiops_ws.get(incident_id, []) + _aiops_ws.get("__all__", [])
    dead = []
    for ws in targets:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        for subscribers in _aiops_ws.values():
            if ws in subscribers:
                subscribers.remove(ws)


@app.post("/api/aiops/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    trigger = {
        "alert_name": "manual",
        "namespace": req.namespace,
        "pod_name": req.pod_name,
        "trigger_source": req.trigger_source,
    }
    asyncio.create_task(run_pipeline(trigger, on_step=_broadcast_step))
    return {"status": "started", "message": "Diagnosis pipeline triggered"}


@app.post("/api/aiops/webhook")
async def alertmanager_webhook(payload: dict) -> dict:
    triggered = []
    for alert in payload.get("alerts", []):
        labels = alert.get("labels", {})
        trigger = {
            "alert_name": labels.get("alertname", "unknown"),
            "namespace": labels.get("namespace", ""),
            "pod_name": labels.get("pod", ""),
            "trigger_source": "alertmanager",
            "severity": labels.get("severity", "warning"),
        }
        asyncio.create_task(run_pipeline(trigger))
        triggered.append(trigger["alert_name"])
    return {"status": "accepted", "alerts": triggered}


@app.get("/api/incidents")
async def incidents(limit: int = 50, status: str = "", severity: str = "") -> list[dict]:
    return await list_incidents(limit=limit, status=status or None, severity=severity or None)


@app.get("/api/incidents/{incident_id}")
async def incident_detail(incident_id: str) -> dict:
    inc = await get_incident(incident_id)
    return inc or {"error": "not found"}


@app.patch("/api/incidents/{incident_id}/status")
async def patch_status(incident_id: str, payload: dict) -> dict:
    await update_incident_status(incident_id, payload.get("status", "RESOLVED"))
    return {"status": "updated"}


@app.websocket("/ws/aiops/{incident_id}")
async def aiops_ws(ws: WebSocket, incident_id: str) -> None:
    await ws.accept()
    _aiops_ws.setdefault(incident_id, []).append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        subscribers = _aiops_ws.get(incident_id, [])
        if ws in subscribers:
            subscribers.remove(ws)
