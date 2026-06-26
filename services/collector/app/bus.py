"""Redis prediction bus.

Each scored flow is both published on a pub/sub channel (live fan-out to the
dashboard via backend-api) and pushed onto a capped list (recent history that a
late-joining client or the metrics endpoints can read).
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis


class PredictionBus:
    def __init__(self, url: str, channel: str, buffer_key: str, buffer_max: int) -> None:
        self._redis = redis.from_url(url, decode_responses=True)
        self.channel = channel
        self.buffer_key = buffer_key
        self.buffer_max = buffer_max

    async def publish(self, result: dict[str, Any]) -> None:
        payload = json.dumps(result, default=str)
        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.publish(self.channel, payload)
            pipe.lpush(self.buffer_key, payload)
            pipe.ltrim(self.buffer_key, 0, self.buffer_max - 1)
            await pipe.execute()

    async def ping(self) -> bool:
        return await self._redis.ping()

    async def close(self) -> None:
        await self._redis.aclose()
