"""Redis consumer — reads the recent buffer and subscribes to the live channel."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis


class PredictionBus:
    def __init__(self, url: str, channel: str, buffer_key: str) -> None:
        self._redis = redis.from_url(url, decode_responses=True)
        self.channel = channel
        self.buffer_key = buffer_key

    async def recent(self, limit: int) -> list[dict[str, Any]]:
        """Return up to ``limit`` recent results, newest first."""
        raw = await self._redis.lrange(self.buffer_key, 0, limit - 1)
        out: list[dict] = []
        for item in raw:
            try:
                out.append(json.loads(item))
            except (ValueError, TypeError):
                continue
        return out

    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        """Yield each prediction published on the channel."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    yield json.loads(message["data"])
                except (ValueError, TypeError):
                    continue
        finally:
            await pubsub.unsubscribe(self.channel)
            await pubsub.aclose()

    async def ping(self) -> bool:
        return await self._redis.ping()

    async def close(self) -> None:
        await self._redis.aclose()
