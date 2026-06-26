"""
PostgreSQL persistence for incidents.

Uses the same PostgreSQL instance as MLflow (mlflow-postgresql in the mlops namespace).
Incidents are stored in a separate 'aiops' database.

For local dev (no DB), falls back to an in-memory store.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

DB_URL = os.getenv(
    "AIOPS_DB_URL",
    "",  # e.g. postgresql://aiops:aiops@mlflow-postgresql.mlops.svc.cluster.local:5432/aiops
)

# In-memory fallback for local dev
_memory_store: dict[str, dict] = {}


async def _get_conn():
    """Return an asyncpg connection or None if DB not configured."""
    if not DB_URL:
        return None
    try:
        import asyncpg
        return await asyncpg.connect(DB_URL)
    except Exception:
        return None


async def save_incident(incident: dict) -> None:
    """Insert or update a full incident record."""
    conn = await _get_conn()
    if conn is None:
        _memory_store[incident["id"]] = incident
        return

    try:
        await conn.execute("""
            INSERT INTO incidents (
                id, triggered_at, trigger_source, trigger_raw, status,
                severity, failure_mode, namespace, affected_pods,
                root_cause, confidence,
                triage_output, evidence_output, rca_output, postmortem,
                duration_s
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            ON CONFLICT (id) DO UPDATE SET
                status         = EXCLUDED.status,
                severity       = EXCLUDED.severity,
                failure_mode   = EXCLUDED.failure_mode,
                namespace      = EXCLUDED.namespace,
                affected_pods  = EXCLUDED.affected_pods,
                root_cause     = EXCLUDED.root_cause,
                confidence     = EXCLUDED.confidence,
                triage_output  = EXCLUDED.triage_output,
                evidence_output= EXCLUDED.evidence_output,
                rca_output     = EXCLUDED.rca_output,
                postmortem     = EXCLUDED.postmortem,
                duration_s     = EXCLUDED.duration_s
        """,
            incident["id"],
            incident.get("triggered_at"),
            incident.get("trigger_source", "manual"),
            json.dumps(incident.get("trigger_raw", {})),
            incident.get("status", "OPEN"),
            incident.get("severity"),
            incident.get("failure_mode"),
            incident.get("namespace"),
            json.dumps(incident.get("affected_pods", [])),
            incident.get("root_cause"),
            incident.get("confidence"),
            json.dumps(incident.get("triage")),
            json.dumps(incident.get("evidence")),
            json.dumps(incident.get("rca")),
            json.dumps(incident.get("postmortem")),
            incident.get("duration_s"),
        )
    finally:
        await conn.close()


async def update_incident_step(incident_id: str, step: str, data: dict) -> None:
    """Update a single agent step result on an existing incident row."""
    col_map = {
        "triage":     "triage_output",
        "evidence":   "evidence_output",
        "rca":        "rca_output",
        "postmortem": "postmortem",
    }
    col = col_map.get(step)
    if not col:
        return

    conn = await _get_conn()
    if conn is None:
        if incident_id in _memory_store:
            _memory_store[incident_id][step] = data
        return

    try:
        await conn.execute(
            f"UPDATE incidents SET {col} = $1 WHERE id = $2",
            json.dumps(data), incident_id,
        )
    finally:
        await conn.close()


async def list_incidents(
    limit: int = 50,
    status: Optional[str] = None,
    severity: Optional[str] = None,
) -> list[dict]:
    """Return a list of incidents (summary fields only, no heavy JSON blobs)."""
    conn = await _get_conn()

    if conn is None:
        rows = list(_memory_store.values())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        if severity:
            rows = [r for r in rows if r.get("severity") == severity]
        rows.sort(key=lambda r: r.get("triggered_at", ""), reverse=True)
        return rows[:limit]

    try:
        filters = []
        params  = []
        if status:
            params.append(status)
            filters.append(f"status = ${len(params)}")
        if severity:
            params.append(severity)
            filters.append(f"severity = ${len(params)}")

        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)

        rows = await conn.fetch(f"""
            SELECT id, triggered_at, trigger_source, status, severity,
                   failure_mode, namespace, affected_pods,
                   root_cause, confidence, duration_s
            FROM incidents
            {where}
            ORDER BY triggered_at DESC
            LIMIT ${len(params)}
        """, *params)

        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def get_incident(incident_id: str) -> Optional[dict]:
    """Return a full incident record including all agent outputs."""
    conn = await _get_conn()

    if conn is None:
        return _memory_store.get(incident_id)

    try:
        row = await conn.fetchrow(
            "SELECT * FROM incidents WHERE id = $1", incident_id
        )
        if not row:
            return None
        result = dict(row)
        # Parse JSONB columns
        for col in ("trigger_raw", "affected_pods", "triage_output",
                    "evidence_output", "rca_output", "postmortem"):
            if isinstance(result.get(col), str):
                result[col] = json.loads(result[col])
        return result
    finally:
        await conn.close()


async def update_incident_status(incident_id: str, status: str) -> None:
    """Mark an incident as RESOLVED or NOISE."""
    conn = await _get_conn()
    if conn is None:
        if incident_id in _memory_store:
            _memory_store[incident_id]["status"] = status
            if status == "RESOLVED":
                _memory_store[incident_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
        return

    try:
        resolved_at = datetime.now(timezone.utc) if status == "RESOLVED" else None
        await conn.execute(
            "UPDATE incidents SET status = $1, resolved_at = $2 WHERE id = $3",
            status, resolved_at, incident_id,
        )
    finally:
        await conn.close()
