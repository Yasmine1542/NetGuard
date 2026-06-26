"""Test fixtures — a Detector wired with lightweight fakes.

The real model.pkl is a 2 MB LightGBM artifact and needs libgomp at runtime, so
unit tests inject deterministic stand-ins instead. This keeps the suite fast and
dependency-free while exercising the encoding, vector-build and formatting logic.
"""

import numpy as np
import pytest

from app.detector import Detector


class _FakeEncoder:
    def __init__(self, classes: list[str]) -> None:
        self.classes_ = classes

    def transform(self, values: list[str]) -> list[int]:
        return [self.classes_.index(values[0])]


class _FakeBooster:
    def feature_importance(self, importance_type: str = "gain"):
        # Real LightGBM returns a numpy array; the detector calls .tolist() on it.
        return np.array([10.0, 5.0, 1.0])


class _FakeModel:
    """Predicts class 1 (attack) with probabilities [0.2, 0.8]."""

    booster_ = _FakeBooster()

    def predict(self, frame):  # noqa: ANN001 - test stub
        return [1]

    def predict_proba(self, frame):  # noqa: ANN001 - test stub
        return [[0.2, 0.8]]


@pytest.fixture
def detector() -> Detector:
    d = Detector("unused")
    d.model = _FakeModel()
    d.feature_names = ["duration", "protocol_type", "src_bytes"]
    d.encoders = {"protocol_type": _FakeEncoder(["tcp", "udp"])}
    d.class_names = ["Normal", "Attack"]
    d.attack_family = {"neptune": "DoS"}
    d._compute_importance()
    return d
