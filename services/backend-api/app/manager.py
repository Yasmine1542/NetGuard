"""WebSocket connection manager — fans Redis messages out to dashboard clients."""

from __future__ import annotations

from typing import Any, Protocol


class WSLike(Protocol):
    async def send_json(self, data: Any) -> None: ...


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WSLike] = []

    @property
    def count(self) -> int:
        return len(self._active)

    def add(self, ws: WSLike) -> None:
        self._active.append(ws)

    def remove(self, ws: WSLike) -> None:
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WSLike] = []
        for ws in self._active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)
