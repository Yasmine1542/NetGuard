"""Fakes for the collector: an in-memory bus and a deterministic inference client."""

from typing import Any

import pytest


class FakeBus:
    def __init__(self) -> None:
        self.published: list[dict] = []

    async def publish(self, result: dict[str, Any]) -> None:
        self.published.append(result)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        pass


class FakeInferenceClient:
    """Echoes the flow back as a minimal prediction result."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def model_info(self) -> dict:
        return {"feature_names": ["duration", "protocol_type", "src_bytes"]}

    async def predict(self, flow: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(flow)
        return {
            "prediction": 1 if flow.get("_label") not in ("normal", None) else 0,
            "is_attack": flow.get("_label") not in ("normal", None),
            "true_label": flow.get("_label", "unknown"),
        }

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_bus() -> FakeBus:
    return FakeBus()


@pytest.fixture
def fake_client() -> FakeInferenceClient:
    return FakeInferenceClient()
