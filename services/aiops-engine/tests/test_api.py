"""API smoke tests. The k8s client is unavailable in CI, so /cluster returns the
package's mock snapshot — deterministic and offline."""

from fastapi.testclient import TestClient

from app import main
from app.aiops import db


def test_healthz():
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_cluster_returns_summary():
    client = TestClient(main.app)
    body = client.get("/cluster").json()
    # mock snapshot reports 4 nodes when off-cluster
    assert "nodes_total" in body


def test_incidents_empty_then_listed(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()
    client = TestClient(main.app)
    assert client.get("/api/incidents").json() == []


def test_webhook_requires_token_when_configured(monkeypatch):
    async def _noop(*args, **kwargs):
        return {}
    monkeypatch.setattr(main, "run_pipeline", _noop)
    monkeypatch.setattr(main.settings, "webhook_token", "s3cret")
    client = TestClient(main.app)
    payload = {"alerts": []}

    assert client.post("/api/aiops/webhook", json=payload).status_code == 401
    assert client.post("/api/aiops/webhook", json=payload,
                       headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.post("/api/aiops/webhook", json=payload,
                     headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
