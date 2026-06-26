"""Tests for the in-memory incident store fallback (no AIOPS_DB_URL set)."""

from app.aiops import db


async def test_save_list_get_and_resolve(monkeypatch):
    # Ensure the in-memory path is used and starts clean.
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()

    incident = {
        "id": "INC-TEST-1",
        "triggered_at": "2026-06-25T10:00:00Z",
        "status": "OPEN",
        "severity": "HIGH",
        "failure_mode": "OOMKilled",
    }
    await db.save_incident(incident)

    listed = await db.list_incidents()
    assert len(listed) == 1
    assert listed[0]["id"] == "INC-TEST-1"

    fetched = await db.get_incident("INC-TEST-1")
    assert fetched["severity"] == "HIGH"

    await db.update_incident_status("INC-TEST-1", "RESOLVED")
    assert db._memory_store["INC-TEST-1"]["status"] == "RESOLVED"


async def test_list_filters_by_status(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "")
    db._memory_store.clear()
    await db.save_incident({"id": "A", "status": "OPEN", "triggered_at": "2"})
    await db.save_incident({"id": "B", "status": "RESOLVED", "triggered_at": "1"})

    only_open = await db.list_incidents(status="OPEN")
    assert [i["id"] for i in only_open] == ["A"]
