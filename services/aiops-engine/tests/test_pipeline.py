"""Orchestration tests — the four agents are mocked, so no Groq calls are made.

Verifies the pipeline sequences the agents, assembles the record, streams steps,
and short-circuits on a 'noise' triage.
"""

from app.aiops import db, pipeline


def _stub_agents(monkeypatch, *, is_noise: bool):
    async def fake_triage(trigger):
        return {
            "is_noise": is_noise,
            "severity": "HIGH",
            "failure_mode": "OOMKilled",
            "affected_namespace": "mlops",
            "affected_pods": ["pod-x"],
        }

    async def fake_evidence(triage):
        return {"log_summary": "oom", "raw_evidence": {}}

    async def fake_rca(triage, evidence):
        return {"root_cause": "memory limit too low", "confidence": 0.9, "severity": "HIGH"}

    async def fake_postmortem(triage, evidence, rca, incident_id):
        return {"title": "OOM in mlflow", "action_items": []}

    monkeypatch.setattr(pipeline, "run_triage", fake_triage)
    monkeypatch.setattr(pipeline, "run_evidence", fake_evidence)
    monkeypatch.setattr(pipeline, "run_rca", fake_rca)
    monkeypatch.setattr(pipeline, "run_postmortem", fake_postmortem)


async def test_full_pipeline_runs_all_agents(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()
    _stub_agents(monkeypatch, is_noise=False)

    steps: list[tuple[str, str]] = []

    async def on_step(step, status, data):
        steps.append((step, status))

    incident = await pipeline.run_pipeline({"trigger_source": "manual"}, on_step=on_step)

    assert incident["status"] == "OPEN"
    assert incident["root_cause"] == "memory limit too low"
    assert incident["confidence"] == 0.9
    assert ("rca", "done") in steps
    assert ("postmortem", "done") in steps


async def test_noise_triage_short_circuits(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()
    _stub_agents(monkeypatch, is_noise=True)

    incident = await pipeline.run_pipeline({"trigger_source": "manual"})

    assert incident["status"] == "NOISE"
    assert incident["evidence"] is None  # evidence agent never ran


async def test_collection_failure_is_inconclusive_not_noise(monkeypatch):
    """A failed collection must mark the incident INCONCLUSIVE, never NOISE,
    and must not run the downstream agents."""
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()

    async def fake_triage(trigger):
        return {
            "collection_failed": True, "is_noise": False,
            "failure_mode": "Unknown", "affected_namespace": "netguard",
        }
    monkeypatch.setattr(pipeline, "run_triage", fake_triage)

    incident = await pipeline.run_pipeline({"trigger_source": "manual"})

    assert incident["status"] == "INCONCLUSIVE"
    assert incident["evidence"] is None
