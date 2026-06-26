"""Pipeline + API tests using the in-memory fakes.

The API test overrides the dependency accessors, so it never enters the real
lifespan (no Redis/httpx connections are attempted).
"""

from fastapi.testclient import TestClient

from app import main
from app.generator import TrafficGenerator
from app.pipeline import score_and_publish


async def test_score_and_publish_flows_through(fake_bus, fake_client):
    gen = TrafficGenerator(real_traffic_sample=10, kdd_test_url="http://unused")
    result = await score_and_publish(gen, fake_client, fake_bus, label="neptune")

    assert result["is_attack"] is True
    assert fake_client.calls[0]["_label"] == "neptune"  # generated flow was scored
    assert fake_bus.published == [result]  # and published exactly once


def test_inject_endpoint_publishes(fake_bus, fake_client):
    gen = TrafficGenerator(real_traffic_sample=10, kdd_test_url="http://unused")
    main.app.dependency_overrides[main.get_gen] = lambda: gen
    main.app.dependency_overrides[main.get_client] = lambda: fake_client
    main.app.dependency_overrides[main.get_bus] = lambda: fake_bus
    try:
        client = TestClient(main.app)  # no context manager → lifespan not run
        resp = client.post("/api/inject?attack_type=smurf")
        assert resp.status_code == 200
        assert resp.json()["true_label"] == "smurf"
        assert len(fake_bus.published) == 1
    finally:
        main.app.dependency_overrides.clear()
