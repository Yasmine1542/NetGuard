"""Unit tests for the Detector scoring logic."""

import pytest

from app.detector import Detector


def test_unloaded_detector_is_not_ready_and_refuses_to_predict():
    d = Detector("unused")
    assert d.ready is False
    with pytest.raises(RuntimeError):
        d.predict({"duration": 1})


def test_predict_returns_attack_result(detector):
    result = detector.predict(
        {"duration": 3, "protocol_type": "tcp", "src_bytes": 100, "_label": "neptune"}
    )
    assert result["prediction"] == 1
    assert result["is_attack"] is True
    assert result["label"] == "Attack"
    assert result["confidence"] == 0.8
    assert result["class_probabilities"] == {"Normal": 0.2, "Attack": 0.8}


def test_categorical_encoding_and_unknown_value_falls_back_to_zero(detector):
    # "tcp" is index 0 in the fake encoder; an unseen value must map to 0, not crash.
    assert detector._encode("protocol_type", "tcp") == 0
    assert detector._encode("protocol_type", "udp") == 1
    assert detector._encode("protocol_type", "never-seen") == 0


def test_meta_fields_are_echoed_into_features(detector):
    result = detector.predict(
        {
            "protocol_type": "tcp",
            "_src_ip": "10.0.0.5",
            "_dst_ip": "10.0.0.9",
            "_src_port": 4444,
            "_dst_port": 80,
            "_label": "neptune",
        }
    )
    assert result["features"]["src_ip"] == "10.0.0.5"
    assert result["features"]["dst_port"] == 80
    assert result["true_family"] == "DoS"  # mapped from attack_family


def test_normal_and_unknown_true_family(detector):
    normal = detector.predict({"protocol_type": "tcp", "_label": "normal"})
    unknown = detector.predict({"protocol_type": "tcp", "_label": "unknown"})
    assert normal["true_family"] == "Normal"
    assert unknown["true_family"] == "unknown"


def test_feature_importance_is_normalised_and_sorted(detector):
    imp = detector.feature_importance
    assert imp[0]["feature"] == "duration"  # highest gain
    assert abs(sum(i["importance"] for i in imp) - 1.0) < 1e-6
