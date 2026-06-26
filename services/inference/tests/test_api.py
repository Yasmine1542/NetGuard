"""API tests — exercise the HTTP surface with a fake detector injected."""

from fastapi.testclient import TestClient

from app import main


def _client_with(detector) -> TestClient:
    main.detector = detector
    return TestClient(main.app)


def test_healthz_is_always_ok():
    client = TestClient(main.app)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_503_when_model_absent():
    from app.detector import Detector

    client = _client_with(Detector("unused"))  # not loaded
    assert client.get("/readyz").status_code == 503


def test_predict_returns_scored_flow_with_latency(detector):
    client = _client_with(detector)
    resp = client.post("/predict", json={"flow": {"protocol_type": "tcp", "_label": "neptune"}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_attack"] is True
    assert "latency_ms" in body and body["latency_ms"] >= 0
    assert "timestamp" in body


def test_predict_503_when_model_absent():
    from app.detector import Detector

    client = _client_with(Detector("unused"))
    assert client.post("/predict", json={"flow": {}}).status_code == 503


def test_model_info_reports_classes_and_features(detector):
    client = _client_with(detector)
    info = client.get("/model-info").json()
    assert info["ready"] is True
    assert info["class_names"] == ["Normal", "Attack"]
    assert info["feature_names"] == ["duration", "protocol_type", "src_bytes"]


def test_metrics_endpoint_exposes_prometheus(detector):
    client = _client_with(detector)
    client.post("/predict", json={"flow": {"protocol_type": "tcp", "_label": "neptune"}})
    body = client.get("/metrics").text
    assert "netguard_predictions_total" in body
    assert "netguard_model_loaded" in body
    assert "netguard_inference_latency_seconds" in body
