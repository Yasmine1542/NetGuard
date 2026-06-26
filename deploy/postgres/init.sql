-- Incident store for aiops-engine.
-- The JSON-bearing columns are TEXT because the lifted db layer round-trips them
-- with json.dumps()/json.loads(); keeping them TEXT avoids any asyncpg/JSONB
-- binding surprises while preserving the exact existing behaviour.
CREATE TABLE IF NOT EXISTS incidents (
    id              TEXT PRIMARY KEY,
    triggered_at    TIMESTAMPTZ,
    trigger_source  TEXT,
    trigger_raw     TEXT,
    status          TEXT,
    severity        TEXT,
    failure_mode    TEXT,
    namespace       TEXT,
    affected_pods   TEXT,
    root_cause      TEXT,
    confidence      DOUBLE PRECISION,
    triage_output   TEXT,
    evidence_output TEXT,
    rca_output      TEXT,
    postmortem      TEXT,
    duration_s      DOUBLE PRECISION,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS incidents_triggered_at_idx ON incidents (triggered_at DESC);
CREATE INDEX IF NOT EXISTS incidents_status_idx ON incidents (status);
