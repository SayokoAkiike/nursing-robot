"""Tests for the PR22 repository functions: rounding_sessions /
patient_interactions / nurse_escalations.

Same style as tests/test_repositories.py -- plain CRUD round-trips against
a per-test SQLite file (the `robot_storage` fixture from conftest.py).
"""
from datetime import datetime

from backend.db import repositories

ROUNDING_SESSION_ROW = {
    "id": "session-1",
    "robot_id": "ROBOT_1",
    "room": "203",
    "patient_id": "PATIENT_A_ROOM_203",
    "status": "ROUNDING",
    "started_at": datetime(2026, 7, 9, 9, 0, 0),
    "ended_at": None,
    "interaction_summary": None,
    "detected_need": None,
    "escalation_level": None,
    "created_at": datetime(2026, 7, 9, 9, 0, 0),
    "updated_at": datetime(2026, 7, 9, 9, 0, 0),
}

PATIENT_INTERACTION_ROW = {
    "rounding_session_id": "session-1",
    "patient_id": "PATIENT_A_ROOM_203",
    "room": "203",
    "prompt": "何かお困りですか？",
    "patient_response": "トイレに行きたいです",
    "input_mode": "simulated",
    "detected_need": "toileting",
    "confidence": "high",
    "created_at": datetime(2026, 7, 9, 9, 1, 0),
}

NURSE_ESCALATION_ROW = {
    "id": "esc-1",
    "rounding_session_id": "session-1",
    "request_id": None,
    "patient_id": "PATIENT_A_ROOM_203",
    "room": "203",
    "summary": "203号室 Patient A がトイレ介助を希望。単独離床リスクあり。",
    "priority": "HIGH",
    "reason": "toileting",
    "suggested_action": "看護師が訪室して介助してください。",
    "status": "PENDING",
    "created_at": datetime(2026, 7, 9, 9, 2, 0),
    "acknowledged_at": None,
    "acknowledged_by": None,
    # Added alongside the escalation-timeout safety net: escalated_count
    # defaults to 0 at the ORM level (NurseEscalationRow.escalated_count's
    # Column default) even though it isn't set explicitly here, but this
    # fixture spells it out (plus the two nullable additions) so this
    # test's exact-equality assertion keeps documenting the full row
    # shape rather than silently passing thanks to an ORM default.
    "escalated_count": 0,
    "last_escalated_at": None,
    "source": "rounding",
}


# ---- rounding_sessions ------------------------------------------------------


def test_insert_and_get_rounding_session(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    assert repositories.get_rounding_session("session-1") == ROUNDING_SESSION_ROW


def test_get_rounding_session_missing_returns_none(robot_storage):
    assert repositories.get_rounding_session("does-not-exist") is None


def test_update_rounding_session_partial_fields(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.update_rounding_session(
        "session-1",
        status="NEED_CLASSIFIED",
        detected_need="toileting",
        escalation_level="HIGH",
    )
    row = repositories.get_rounding_session("session-1")
    assert row["status"] == "NEED_CLASSIFIED"
    assert row["detected_need"] == "toileting"
    assert row["escalation_level"] == "HIGH"
    # Untouched fields survive the partial update.
    assert row["room"] == "203"
    assert row["robot_id"] == "ROBOT_1"


def test_list_active_rounding_sessions_excludes_terminal_states(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    completed = dict(ROUNDING_SESSION_ROW, id="session-2", status="COMPLETED")
    repositories.insert_rounding_session(completed)

    active = repositories.list_active_rounding_sessions()
    assert [s["id"] for s in active] == ["session-1"]


def test_list_active_rounding_sessions_filters_by_robot(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    other_robot = dict(ROUNDING_SESSION_ROW, id="session-2", robot_id="ROBOT_2")
    repositories.insert_rounding_session(other_robot)

    active = repositories.list_active_rounding_sessions(robot_id="ROBOT_2")
    assert [s["id"] for s in active] == ["session-2"]


# ---- patient_interactions ----------------------------------------------------


def test_insert_and_list_patient_interactions(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.insert_patient_interaction(PATIENT_INTERACTION_ROW)

    rows = repositories.list_patient_interactions("session-1")
    assert len(rows) == 1
    assert rows[0]["patient_response"] == "トイレに行きたいです"
    assert rows[0]["detected_need"] == "toileting"


def test_list_patient_interactions_ordered_and_scoped_to_session(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    other_session = dict(ROUNDING_SESSION_ROW, id="session-2")
    repositories.insert_rounding_session(other_session)

    repositories.insert_patient_interaction(PATIENT_INTERACTION_ROW)
    repositories.insert_patient_interaction(
        dict(PATIENT_INTERACTION_ROW, patient_response="お水が欲しいです", detected_need="water")
    )
    repositories.insert_patient_interaction(
        dict(PATIENT_INTERACTION_ROW, rounding_session_id="session-2", detected_need="pain")
    )

    rows = repositories.list_patient_interactions("session-1")
    assert [r["detected_need"] for r in rows] == ["toileting", "water"]


# ---- nurse_escalations --------------------------------------------------------


def test_insert_and_get_nurse_escalation(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.insert_nurse_escalation(NURSE_ESCALATION_ROW)

    row = repositories.get_nurse_escalation("esc-1")
    assert row == NURSE_ESCALATION_ROW


def test_list_nurse_escalations_filters_by_status(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.insert_nurse_escalation(NURSE_ESCALATION_ROW)
    acked = dict(NURSE_ESCALATION_ROW, id="esc-2", status="ACKNOWLEDGED")
    repositories.insert_nurse_escalation(acked)

    pending = repositories.list_nurse_escalations(status="PENDING")
    assert [e["id"] for e in pending] == ["esc-1"]

    all_rows = repositories.list_nurse_escalations()
    assert {e["id"] for e in all_rows} == {"esc-1", "esc-2"}


def test_acknowledge_nurse_escalation(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.insert_nurse_escalation(NURSE_ESCALATION_ROW)

    ack_time = datetime(2026, 7, 9, 9, 5, 0)
    repositories.acknowledge_nurse_escalation("esc-1", "nurse_demo", ack_time)

    row = repositories.get_nurse_escalation("esc-1")
    assert row["status"] == "ACKNOWLEDGED"
    assert row["acknowledged_by"] == "nurse_demo"
    assert row["acknowledged_at"] == ack_time


def test_acknowledge_nurse_escalation_missing_id_is_noop(robot_storage):
    # Should not raise -- mirrors update_task_state's "row is None -> skip"
    # behavior for an unknown id.
    repositories.acknowledge_nurse_escalation("does-not-exist", "nurse_demo", datetime.now())


# ---- delete_all_data ----------------------------------------------------------


def test_delete_all_data_clears_rounding_tables_too(robot_storage):
    repositories.insert_rounding_session(ROUNDING_SESSION_ROW)
    repositories.insert_patient_interaction(PATIENT_INTERACTION_ROW)
    repositories.insert_nurse_escalation(NURSE_ESCALATION_ROW)

    repositories.delete_all_data()

    assert repositories.get_rounding_session("session-1") is None
    assert repositories.list_patient_interactions("session-1") == []
    assert repositories.get_nurse_escalation("esc-1") is None
