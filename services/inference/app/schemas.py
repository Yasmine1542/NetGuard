"""Request/response contracts for the inference service."""

from typing import Any

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    """A single raw flow to score.

    ``flow`` holds the NSL-KDD feature dict (the 41 named features) plus optional
    metadata keys the model ignores but the result echoes back: ``_src_ip``,
    ``_dst_ip``, ``_src_port``, ``_dst_port`` and ``_label`` (ground truth, or
    ``"unknown"`` for live traffic).
    """

    flow: dict[str, Any] = Field(..., description="Raw NSL-KDD flow features + optional _meta keys")


class ModelInfo(BaseModel):
    """Static description of the loaded model — consumed by the dashboard and by
    the collector (which needs ``feature_names`` to replay labelled traffic)."""

    ready: bool
    class_names: list[str]
    num_classes: int
    feature_names: list[str]
    metrics: dict[str, Any]
    feature_importance: list[dict[str, Any]]
