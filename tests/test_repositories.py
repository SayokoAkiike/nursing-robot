"""Tests for backend.db.repositories (PR3 rewrite: plain CRUD over
care_requests / robot_tasks / kit_verifications / robot_events, replacing
PR2's singleton-shaped load_state/save_state)."""
from backend.db import repositories

REQUEST_ROW = {
    "id": "req-1",
    "patient_id": "PATIENT_A_ROOM_203",
    "request_type": "toileting",
    "priority": "転倒リスクあり",
    "status": "ASSIGNED",
    "created_at": "2026-07-08T00:00:00",
    "completed_at": None,
}

TASK_ROW = {
    "id": "task-1",
    "request_id": "req-1",
    "robot_id": "ROBOT_1",
    "state": "REQUEST_RECEIVED",
    "kit_id": "KIT_TOILETING_A",
    "assigned_at": "2026-07-08T00:00:00",
    "updated_at": "2026-07-08T00:00:00",
}


def test_get_care_request_missing_returns_none(robot_storage):
    assert repositories.get_care_request("does-not-exist") is None


def test_insert_and_get_care_request(robot_storage):
    repositories.insert_care_request(REQUEST_ROW)
    assert repositories.get_care_request("req-1") == REQUEST_ROW


def test_update_care_request_status(robot_storage):
    repositories.insert_care_request(REQUEST_ROW)
    repositories.update_care_request_status("req-1", "COMPLETED", completed_at="2026-07-08T01:00:00")
    row = repositories.get_care_request("req-1")
    assert row["status"] == "COMPLETED"
    assert row["completed_at"] == "2026-07-08T01:00:00"


def test_insert_and_get_task_by_request_id(robot_storage):
    repositories.insert_robot_task(TASK_ROW)
    assert repositories.get_task_by_request_id("req-1") == TASK_ROW
    assert repositories.get_task_by_request_id("no-such-request") is None


def test_update_task_state(robot_storage):
    repositories.insert_robot_task(TASK_ROW)
    repositories.update_task_state("task-1", "KIT_SELECTED", "2026-07-08T00:05:00")
    task = repositories.get_task_by_request_id("req-1")
    assert task["state"] == "KIT_SELECTED"
    assert task["updated_at"] == "2026-07-08T00:05:00"


def test_active_task_excludes_idle_completed_error(robot_storage):
    repositories.insert_robot_task(TASK_ROW)
    assert repositories.get_active_task_for_robot("ROBOT_1") is not None

    for terminal in ("IDLE", "COMPLETED", "ERROR"):
        repositories.update_task_state("task-1", terminal, "2026-07-08T00:10:00")
        assert repositories.get_active_task_for_robot("ROBOT_1") is None
        repositories.update_task_state("task-1", "REQUEST_RECEIVED", "2026-07-08T00:00:00")


def test_active_task_is_scoped_per_robot(robot_storage):
    repositories.insert_robot_task(TASK_ROW)
    assert repositories.get_active_task_for_robot("ROBOT_1") is not None
    assert repositories.get_active_task_for_robot("ROBOT_2") is None


def test_list_active_tasks_hides_only_idle(robot_storage):
    repositories.insert_robot_task(TASK_ROW)
    assert len(repositories.list_active_tasks()) == 1

    repositories.update_task_state("task-1", "COMPLETED", "2026-07-08T00:10:00")
    assert len(repositories.list_active_tasks()) == 1  # still visible

    repositories.update_task_state("task-1", "IDLE", "2026-07-08T00:20:00")
    assert len(repositories.list_active_tasks()) == 0  # hidden


def test_kit_verification_insert_and_list(robot_storage):
    repositories.insert_kit_verification(
        {
            "task_id": "task-1",
            "patient_id": "PATIENT_A_ROOM_203",
            "kit_id": "KIT_TOILETING_A",
            "result": "OK",
            "message": "照合OK",
            "created_at": "2026-07-08T00:00:00",
        }
    )
    repositories.insert_kit_verification(
        {
            "task_id": "task-1",
            "patient_id": "PATIENT_B_ROOM_204",
            "kit_id": "KIT_TOILETING_A",
            "result": "NG",
            "message": "患者ID不一致",
            "created_at": "2026-07-08T00:01:00",
        }
    )
    results = repositories.list_kit_verifications_for_task("task-1")
    assert [r["result"] for r in results] == ["OK", "NG"]


def test_logs_append_and_order(robot_storage):
    repositories.append_log_entry({"timestamp": "t1", "event_type": "REQUEST_CREATED"})
    repositories.append_log_entry({"timestamp": "t2", "event_type": "STATE_TRANSITION"})
    logs = repositories.load_logs()
    assert [entry["event_type"] for entry in logs] == ["REQUEST_CREATED", "STATE_TRANSITION"]

