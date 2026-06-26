"""Thin async client for the inference service."""

from __future__ import annotations

from typing import Any

import httpx


class InferenceClient:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def model_info(self) -> dict[str, Any] | None:
        try:
            r = await self._client.get("/model-info")
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    async def predict(self, flow: dict[str, Any]) -> dict[str, Any]:
        r = await self._client.post("/predict", json={"flow": flow})
        r.raise_for_status()
        return r.json()

    async def close(self) -> None:
        await self._client.aclose()
