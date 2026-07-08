"""Tests for backend.db.repositories, the SQLAlchemy-backed persistence
facade introduced in PR2 (replacing PR1's JSON-file-backed version).
 
Each test gets its own SQLite file via the `robot_storage` fixture (see
tests/conftest.py) -- the same per-test isolation PR1 used for the JSON
file, just pointed at a database instead.
"""
from backend.db import repositories
 
 
def test_load_state_defaults_to_idle(robot_storage):
    assert repositories.load_state() == {"request": None, "robot_state": "IDLE"}
 
 
def test_save_and_load_state_roundtrip(robot_storage):
    state = {
        "request_id": "abc123",
        "request_type": "toileting",
        "request": "Toileting preparation",
        "kit": "KIT_TOILETING_A",
        "risk": "転倒リスクあり",
        "patient_id": "PATIENT_A_ROOM_203",
        "robot_state": "REQUEST_RECEIVED",
        "timestamp": "2026-07-08T00:00:00",
    }
    repositories.save_state(state)
    assert repositories.load_state() == state
 
 
def test_save_state_clears_previous_row(robot_storage):
    repositories.save_state({"request_id": "first", "robot_state": "REQUEST_RECEIVED"})
    repositories.save_state({"request": None, "robot_state": "IDLE"})
    assert repositories.load_state() == {"request": None, "robot_state": "IDLE"}
 
 
def test_get_request_by_id(robot_storage):
    repositories.save_state({"request_id": "xyz", "robot_state": "REQUEST_RECEIVED"})
    assert repositories.get_request("xyz")["robot_state"] == "REQUEST_RECEIVED"
    assert repositories.get_request("does-not-exist") is None
 
 
def test_list_requests_reflects_idle_vs_active(robot_storage):
    assert repositories.list_requests() == []
    repositories.save_state({"request_id": "abc", "robot_state": "REQUEST_RECEIVED"})
    assert len(repositories.list_requests()) == 1
 
 
def test_logs_append_and_order(robot_storage):
    repositories.append_log_entry({"timestamp": "t1", "event_type": "REQUEST_CREATED"})
    repositories.append_log_entry({"timestamp": "t2", "event_type": "STATE_TRANSITION"})
    logs = repositories.load_logs()
    assert [entry["event_type"] for entry in logs] == ["REQUEST_CREATED", "STATE_TRANSITION"]
 
