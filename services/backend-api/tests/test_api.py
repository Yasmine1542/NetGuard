"""API tests with fake bus + upstreams injected (no Redis/network)."""

from fastapi.testclient import TestClient

from app import main


class FakeBus:
    def __init__(self, records):
        self._records = records

    async def recent(self, limit):
        return self._records[:limit]

    async def ping(self):
        return True


class FakeUpstreams:
    async def model_info(self):
        return {"ready": True, "class_names": ["Normal", "Attack"], "num_classes": 2,
                "metrics": {"f1": 0.9}, "feature_importance": []}

    async def cluster_summary(self):
        return {"nodes_total": 4, "pods_total": 30, "nodes_ready": 4, "pods_unhealthy": 1}

    async def prometheus(self, *a, **k):
        return {"status": "success", "echo": a}

    async def loki(self, *a, **k):
        return {"status": "success"}


def _client(records=None) -> TestClient:
    main.app.dependency_overrides[main.get_bus] = lambda: FakeBus(records or [])
    main.app.dependency_overrides[main.get_upstreams] = lambda: FakeUpstreams()
    return TestClient(main.app)


def teardown_function() -> None:
    main.app.dependency_overrides.clear()


def test_status_aggregates_model_info():
    body = _client().get("/api/status").json()
    assert body["model"] is True
    assert body["class_names"] == ["Normal", "Attack"]
    assert body["metrics"]["f1"] == 0.9


def test_metrics_merges_session_and_cluster():
    records = [{"is_attack": True, "label": "DoS", "latency_ms": 5.0, "timestamp": 2}]
    body = _client(records).get("/api/metrics").json()
    assert body["predictions_total"] == 1
    assert body["node_count"] == 4
    assert body["pods_unhealthy"] == 1
    assert "cpu_usage_percent" in body


def test_prometheus_proxy_passthrough():
    body = _client().get("/api/prometheus?query=up").json()
    assert body["status"] == "success"
