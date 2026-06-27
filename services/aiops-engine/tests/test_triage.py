"""Triage collection-failure handling (B2).

A Kubernetes API error from a collector must produce an INCONCLUSIVE result
(collection_failed=True, is_noise=False) WITHOUT calling the LLM — graceful
degradation must never look like an all-clear.
"""

from app.aiops.agents import triage


async def test_collection_failure_is_inconclusive_and_skips_llm(monkeypatch):
    # The unhealthy-pods collector returns an API error.
    monkeypatch.setattr(triage, "list_unhealthy_pods", lambda ns=None: [{"error": "api timeout"}])
    monkeypatch.setattr(triage, "get_node_status", lambda: [])

    # The LLM must never be reached on a collection failure.
    def _boom(*args, **kwargs):
        raise AssertionError("LLM must not be called when collection failed")
    monkeypatch.setattr(triage, "get_llm", _boom)

    out = await triage.run_triage({"namespace": "", "pod_name": "", "trigger_source": "manual"})

    assert out["collection_failed"] is True
    assert out["is_noise"] is False
    assert "inconclusive" in out["summary"].lower()


def test_has_error_detects_api_errors():
    assert triage._has_error([{"error": "boom"}]) is True
    assert triage._has_error([{"status": "all pods healthy"}]) is False
    assert triage._has_error([]) is False
