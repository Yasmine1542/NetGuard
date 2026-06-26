"""Core generate → score → publish step, isolated for testability."""

from __future__ import annotations

from typing import Any

from .bus import PredictionBus
from .generator import TrafficGenerator
from .inference_client import InferenceClient


async def score_and_publish(
    gen: TrafficGenerator,
    client: InferenceClient,
    bus: PredictionBus,
    label: str | None = None,
) -> dict[str, Any]:
    """Generate one flow, score it via inference, publish the result, return it."""
    flow = gen.sample(label=label)
    result = await client.predict(flow)
    await bus.publish(result)
    return result
