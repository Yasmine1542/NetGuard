"""Tests for the WebSocket connection manager fan-out."""

from app.manager import ConnectionManager


class FakeWS:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list = []
        self.fail = fail

    async def send_json(self, data) -> None:
        if self.fail:
            raise RuntimeError("broken socket")
        self.sent.append(data)


async def test_broadcast_reaches_all_live_clients():
    m = ConnectionManager()
    a, b = FakeWS(), FakeWS()
    m.add(a)
    m.add(b)
    await m.broadcast({"type": "prediction", "data": 1})
    assert a.sent == [{"type": "prediction", "data": 1}]
    assert b.sent == [{"type": "prediction", "data": 1}]


async def test_broadcast_drops_dead_clients():
    m = ConnectionManager()
    good, dead = FakeWS(), FakeWS(fail=True)
    m.add(good)
    m.add(dead)
    await m.broadcast({"x": 1})
    assert m.count == 1  # the dead socket was pruned
    assert good.sent == [{"x": 1}]
