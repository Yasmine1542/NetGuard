"""
PostgreSQL persistence for incidents (JSONB columns via an asyncpg codec).

In the cluster this targets the netguard `postgres` StatefulSet, selected by
AIOPS_DB_URL. JSON-bearing columns are JSONB so they can be queried and
aggregated (e.g. for the evaluation and the incident-memory plan). For local dev
(no DB), it falls back to an in-memory store.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

DB_URL = os.getenv(
    "AIOPS_DB_URL",
    "",  # e.g. postgresql://aiops:<pw>@postgres.netguard.svc.cluster.local:5432/aiops
)

# In-memory fallback for local dev
_memory_store: dict[str, dict] = {}


def _as_dt(value):
    """Coerce an ISO timestamp string to a datetime for TIMESTAMPTZ columns
    (asyncpg rejects plain strings). Accepts a trailing 'Z'."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _get_conn():
    """Return an asyncpg connection (with a JSONB codec) or None if not configured."""
    if not DB_URL:
        return None
    try:
        import asyncpg
        conn = await asyncpg.connect(DB_URL)
        # Encode/decode JSONB as Python objects, so we store dicts/lists directly
        # and reads come back parsed — enabling WHERE/aggregation over the data
        # (e.g. WHERE (rca_output->>'confidence')::float > 0.8) and the memory plan.
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )
        return conn
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
            _as_dt(incident.get("triggered_at")),
            incident.get("trigger_source", "manual"),
            incident.get("trigger_raw", {}),
            incident.get("status", "OPEN"),
            incident.get("severity"),
            incident.get("failure_mode"),
            incident.get("namespace"),
            incident.get("affected_pods", []),
            incident.get("root_cause"),
            incident.get("confidence"),
            incident.get("triage"),
            incident.get("evidence"),
            incident.get("rca"),
            incident.get("postmortem"),
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
            data, incident_id,
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
        # JSONB columns are already decoded to dicts/lists by the codec.
        return dict(row)
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
