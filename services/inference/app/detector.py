"""LightGBM intrusion detector.

Loads the NSL-KDD artifacts once and scores raw flow dicts. The scoring logic is
lifted verbatim from the original monolith (feature encoding, vector build,
5-class formatting) so behaviour is unchanged — only the packaging is new.
"""

from __future__ import annotations

import json
import os
from typing import Any

import joblib
import pandas as pd

CATEGORICAL_COLS = ("protocol_type", "service", "flag")


def _read_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


class Detector:
    """Owns the model and exposes a single ``predict(flow) -> result`` call."""

    def __init__(self, model_dir: str) -> None:
        self.model_dir = model_dir
        self.model: Any = None
        self.encoders: dict[str, Any] = {}
        self.feature_names: list[str] = []
        self.class_names: list[str] = ["Normal", "DoS", "Probe", "R2L", "U2R"]
        self.attack_family: dict[str, str] = {}
        self.metrics: dict[str, Any] = {}
        self.feature_importance: list[dict[str, Any]] = []

    @property
    def ready(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        """Load model + encoders + metadata from ``model_dir``.

        Raises FileNotFoundError if the artifacts are missing, so the caller can
        decide whether to fail fast or stay unready.
        """
        d = self.model_dir
        self.model = joblib.load(os.path.join(d, "model.pkl"))
        self.encoders = joblib.load(os.path.join(d, "encoders.pkl"))
        self.feature_names = _read_json(os.path.join(d, "feature_names.json"))
        self.attack_family = _read_json(os.path.join(d, "attack_family.json"))

        # class_names.json is written by the 5-class trainer; older binary models
        # omit it, in which case the default 5-class list above is kept.
        cn_path = os.path.join(d, "class_names.json")
        if os.path.exists(cn_path):
            self.class_names = _read_json(cn_path)

        raw_metrics = _read_json(os.path.join(d, "metrics.json"))
        if "overall" in raw_metrics:  # new nested format
            self.metrics = {**raw_metrics["overall"], "per_class": raw_metrics.get("per_class", {})}
        else:  # legacy flat format
            self.metrics = raw_metrics

        self._compute_importance()

    def _compute_importance(self) -> None:
        m = self.model
        if hasattr(m, "booster_") and self.feature_names:
            gains = m.booster_.feature_importance(importance_type="gain").tolist()
            total = float(sum(gains)) or 1.0
            top = sorted(zip(self.feature_names, gains, strict=False), key=lambda x: -x[1])[:10]
            self.feature_importance = [
                {"feature": f, "importance": round(g / total, 4)} for f, g in top
            ]

    def _encode(self, col: str, val: str) -> int:
        le = self.encoders.get(col)
        if le is not None and val in le.classes_:
            return int(le.transform([val])[0])
        return 0

    def _vector(self, flow: dict[str, Any]) -> list[float]:
        vector: list[float] = []
        for col in self.feature_names:
            val = flow.get(col, 0)
            if col in CATEGORICAL_COLS:
                val = self._encode(col, str(val))
            vector.append(float(val))
        return vector

    def predict(self, flow: dict[str, Any]) -> dict[str, Any]:
        """Score one flow. Returns the rich result dict the dashboard consumes."""
        if not self.ready:
            raise RuntimeError("model not loaded")

        frame = pd.DataFrame([self._vector(flow)], columns=self.feature_names)
        pred = int(self.model.predict(frame)[0])
        proba = [float(p) for p in self.model.predict_proba(frame)[0]]
        return self._format(flow, pred, proba)

    def _format(self, flow: dict[str, Any], pred: int, proba: list[float]) -> dict[str, Any]:
        label = flow.get("_label", "unknown")
        pred_class = self.class_names[pred] if pred < len(self.class_names) else "Unknown"
        is_attack = pred > 0
        confidence = round(proba[pred], 4) if pred < len(proba) else 0.0

        if label == "normal":
            true_family = "Normal"
        elif label == "unknown":
            true_family = "unknown"
        else:
            true_family = self.attack_family.get(label.lower(), "U2R")

        return {
            "prediction": pred,
            "label": pred_class,
            "attack_type": pred_class,
            "is_attack": is_attack,
            "confidence": confidence,
            "class_probabilities": {
                self.class_names[i]: round(p, 4)
                for i, p in enumerate(proba)
                if i < len(self.class_names)
            },
            "features": {
                "protocol": flow.get("protocol_type", "?"),
                "service": flow.get("service", "?"),
                "src_bytes": flow.get("src_bytes", 0),
                "dst_bytes": flow.get("dst_bytes", 0),
                "flag": flow.get("flag", "?"),
                "src_ip": flow.get("_src_ip", "0.0.0.0"),
                "dst_ip": flow.get("_dst_ip", "0.0.0.0"),
                "src_port": flow.get("_src_port", 0),
                "dst_port": flow.get("_dst_port", 0),
            },
            "true_label": label,
            "true_family": true_family,
        }
