"""Unit tests for the traffic generator."""

from app.generator import TrafficGenerator

# A few representative NSL-KDD feature names; the real model has 41.
SAMPLE_FEATURES = ["duration", "protocol_type", "service", "flag", "src_bytes"]


def _gen() -> TrafficGenerator:
    return TrafficGenerator(real_traffic_sample=10, kdd_test_url="http://unused")


def test_synthetic_normal_flow_has_meta_and_label():
    flow = _gen().sample(label="normal")
    assert flow["_label"] == "normal"
    assert flow["flag"] == "SF"  # normal flows complete
    for key in ("_src_ip", "_dst_ip", "_src_port", "_dst_port", "protocol_type"):
        assert key in flow


def test_synthetic_attack_flow_is_distinct():
    flow = _gen().sample(label="neptune")
    assert flow["_label"] == "neptune"
    assert flow["flag"] in ("S0", "REJ", "RSTO", "SH")


def test_random_sample_without_label_still_valid():
    flow = _gen().sample()
    assert "_label" in flow and "count" in flow


def test_replay_used_when_real_traffic_loaded():
    g = _gen()
    g.set_feature_names(SAMPLE_FEATURES)
    g._real_records = [{"_label": "smurf", "service": "http", "replayed": True}]
    g._real_by_label = {"smurf": g._real_records}
    assert g.has_real_traffic is True
    assert g.sample(label="smurf")["replayed"] is True


def test_row_to_raw_rejects_short_rows():
    g = _gen()
    g.set_feature_names(SAMPLE_FEATURES)
    assert g._row_to_raw(["tcp", "http"]) is None  # too few fields
