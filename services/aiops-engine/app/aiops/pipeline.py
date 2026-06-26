"""
Orchestrator — runs the 4 agents in sequence and assembles the incident record.

Flow: Triage → Evidence → RCA → Postmortem → Store

Each agent receives the output of the previous agent as input.
A step_callback is called after each agent completes so the dashboard
can stream progress via WebSocket.
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

from .agents.triage     import run_triage
from .agents.evidence   import run_evidence
from .agents.rca        import run_rca
from .agents.postmortem import run_postmortem
from .db                import save_incident, update_incident_step


StepCallback = Callable[[str, str, dict], Awaitable[None]]


async def _noop_callback(step: str, status: str, data: dict) -> None:
    pass


async def run_pipeline(
    trigger: dict,
    on_step: StepCallback = _noop_callback,
) -> dict:
    """
    Run the full 4-agent incident diagnosis pipeline.

    Args:
        trigger: dict with keys: alert_name, namespace, pod_name (optional),
                 trigger_source ('alertmanager'|'manual'|'scheduled')
        on_step: async callback called after each agent with
                 (step_name, status, output_dict)

    Returns:
        Full incident record dict.
    """
    incident_id  = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    triggered_at = datetime.now(timezone.utc).isoformat()
    start_time   = time.perf_counter()

    incident = {
        "id":             incident_id,
        "triggered_at":   triggered_at,
        "trigger_source": trigger.get("trigger_source", "manual"),
        "trigger_raw":    trigger,
        "status":         "ANALYZING",
        "triage":         None,
        "evidence":       None,
        "rca":            None,
        "postmortem":     None,
        "duration_s":     None,
    }

    # Persist initial record so dashboard can show "analyzing" state
    await save_incident(incident)
    await on_step("pipeline", "started", {"incident_id": incident_id})

    # ── Step 1: Triage ────────────────────────────────────────────────
    await on_step("triage", "running", {})
    triage_output = await run_triage(trigger)
    incident["triage"] = triage_output
    await update_incident_step(incident_id, "triage", triage_output)
    await on_step("triage", "done", triage_output)

    # If triage says this is noise, stop early
    if triage_output.get("is_noise", False):
        incident["status"] = "NOISE"
        incident["duration_s"] = round(time.perf_counter() - start_time, 1)
        await save_incident(incident)
        await on_step("pipeline", "noise", incident)
        return incident

    # ── Step 2: Evidence ──────────────────────────────────────────────
    await on_step("evidence", "running", {})
    evidence_output = await run_evidence(triage_output)
    incident["evidence"] = evidence_output
    await update_incident_step(incident_id, "evidence", evidence_output)
    await on_step("evidence", "done", evidence_output)

    # ── Step 3: RCA ───────────────────────────────────────────────────
    await on_step("rca", "running", {})
    rca_output = await run_rca(triage_output, evidence_output)
    incident["rca"] = rca_output
    await update_incident_step(incident_id, "rca", rca_output)
    await on_step("rca", "done", rca_output)

    # ── Step 4: Postmortem ────────────────────────────────────────────
    await on_step("postmortem", "running", {})
    postmortem_output = await run_postmortem(
        triage_output, evidence_output, rca_output, incident_id
    )
    incident["postmortem"] = postmortem_output
    await update_incident_step(incident_id, "postmortem", postmortem_output)
    await on_step("postmortem", "done", postmortem_output)

    # ── Finalize ──────────────────────────────────────────────────────
    incident["status"]     = "OPEN"
    incident["severity"]   = rca_output.get("severity",      triage_output.get("severity", "LOW"))
    incident["failure_mode"] = triage_output.get("failure_mode", "Unknown")
    incident["namespace"]  = triage_output.get("affected_namespace", "unknown")
    incident["affected_pods"] = triage_output.get("affected_pods", [])
    incident["root_cause"] = rca_output.get("root_cause", "")
    incident["confidence"] = rca_output.get("confidence", 0.0)
    incident["duration_s"] = round(time.perf_counter() - start_time, 1)

    await save_incident(incident)
    await on_step("pipeline", "complete", incident)

    return incident
