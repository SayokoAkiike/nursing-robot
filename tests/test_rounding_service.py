"""Tests for backend.services.rounding_service.

Same fixture style as tests/test_workflow_service.py: the `robot_storage`
fixture from conftest.py gives each test an independent SQLite file.
"""
import pytest

from backend.core.errors import ConflictError, DomainError, NotFoundError
from backend.db import repositories
from backend.services import rounding_service


def test_start_rounding_creates_session_in_rounding_state(robot_storage):
    session = rounding_service.start_rounding("203")
    assert session["status"] == "ROUNDING"
    assert session["room"] == "203"
    assert session["robot_id"] == "ROBOT_1"
    assert session["patient_id"] is None


def test_detect_patient_advances_state_and_sets_patient_id(robot_storage):
    session = rounding_service.start_rounding("203")
    updated = rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    assert updated["status"] == "PATIENT_DETECTED"
    assert updated["patient_id"] == "PATIENT_A_ROOM_203"


def test_start_interaction_advances_through_approaching_to_interaction_started(robot_storage):
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    result = rounding_service.start_interaction(session["id"])
    assert result["session"]["status"] == "INTERACTION_STARTED"
    assert "prompt" in result and result["prompt"]


def _to_interaction_started(session_id: str) -> None:
    rounding_service.detect_patient(session_id, "PATIENT_A_ROOM_203")
    rounding_service.start_interaction(session_id)


def test_classify_need_toileting_detects_high_priority_and_stays_at_need_classified(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])

    result = rounding_service.classify_need(session["id"], "トイレに行きたいです")
    assert result["detected_need"] == "toileting"
    assert result["escalation_level"] == "HIGH"
    assert result["route"] == "NURSE_NOTIFICATION"
    assert result["session"]["status"] == "NEED_CLASSIFIED"
    assert "203" in result["summary"]


def test_classify_need_records_patient_interaction(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "お水が飲みたいです")

    interactions = repositories.list_patient_interactions(session["id"])
    assert len(interactions) == 1
    assert interactions[0]["patient_response"] == "お水が飲みたいです"
    assert interactions[0]["detected_need"] == "water"


def test_pain_response_urgent_escalation_route(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    result = rounding_service.classify_need(session["id"], "胸が痛いです")
    assert result["route"] == "URGENT_ESCALATION"
    assert result["escalation_level"] == "URGENT"


def test_provide_information_completes_session_without_escalation(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "大丈夫です")

    result = rounding_service.provide_information(session["id"])
    assert result["status"] == "COMPLETED"
    assert result["ended_at"] is not None
    # No escalation should have been raised.
    assert repositories.list_nurse_escalations() == []


def test_escalate_creates_pending_escalation_and_moves_to_waiting_for_ack(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    classification = rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.escalate(
        session["id"],
        summary=classification["summary"],
        priority=classification["escalation_level"],
        suggested_action=classification["suggested_action"],
        reason="toileting",
        route=classification["route"],
    )
    assert result["session"]["status"] == "WAITING_FOR_NURSE_ACK"

    escalation = repositories.get_nurse_escalation(result["escalation_id"])
    assert escalation["status"] == "PENDING"
    assert escalation["priority"] == "HIGH"
    assert escalation["rounding_session_id"] == session["id"]


def test_require_delivery_creates_real_care_request_and_task(robot_storage):
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.require_delivery(session["id"], "toileting")
    request = repositories.get_care_request(result["request_id"])
    assert request is not None
    assert request["source"] == "robot_rounding"
    assert request["rounding_session_id"] == session["id"]

    task = repositories.get_task_by_request_id(result["request_id"])
    assert task is not None
    assert task["state"] == "REQUEST_RECEIVED"

    assert result["session"]["status"] == "DELIVERY_REQUIRED"


def test_require_delivery_assigns_to_sessions_own_robot_id(robot_storage):
    """Item 5: a rounding session started on a non-default robot must hand
    its delivery request to that same robot, not silently to
    workflow_service.DEFAULT_ROBOT_ID -- the exact gap
    test_workflow_service.py's test_concurrency_guard_is_per_robot_not_
    global first documented (data model supports it, but require_delivery
    used to ignore it)."""
    session = rounding_service.start_rounding("204", robot_id="ROBOT_2")
    rounding_service.detect_patient(session["id"], "PATIENT_B_ROOM_204")
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    result = rounding_service.require_delivery(session["id"], "toileting")

    task = repositories.get_task_by_request_id(result["request_id"])
    assert task is not None
    assert task["robot_id"] == "ROBOT_2"


def test_require_delivery_without_patient_id_raises(robot_storage):
    # start_rounding -> detect_patient not called -> no patient_id anywhere.
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "")  # falsy patient_id
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")

    with pytest.raises(DomainError):
        rounding_service.require_delivery(session["id"], "toileting")


def test_acknowledge_and_complete_moves_through_nurse_acknowledged_to_completed(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )

    result = rounding_service.acknowledge_and_complete(session["id"])
    assert result["status"] == "COMPLETED"
    assert result["ended_at"] is not None


def test_get_session_missing_raises_not_found(robot_storage):
    with pytest.raises(NotFoundError):
        rounding_service.get_session("does-not-exist")


def test_list_active_sessions_excludes_completed(robot_storage):
    s1 = rounding_service.start_rounding("203")
    s2 = rounding_service.start_rounding("204")
    _to_interaction_started(s2["id"])
    rounding_service.classify_need(s2["id"], "大丈夫です")
    rounding_service.provide_information(s2["id"])

    active = rounding_service.list_active_sessions()
    assert [s["id"] for s in active] == [s1["id"]]


# ---- Safety regression tests (mirrors proposal doc section 9) --------------


def test_cannot_skip_from_rounding_directly_to_need_classified(robot_storage):
    session = rounding_service.start_rounding("203")
    with pytest.raises(ConflictError):
        rounding_service._advance(session["id"], "ROUNDING", "NEED_CLASSIFIED")


def test_waiting_for_nurse_ack_does_not_auto_advance_to_completed(robot_storage):
    """The one-way gate: an escalated session sits at WAITING_FOR_NURSE_ACK
    until something explicitly calls acknowledge_and_complete(). Nothing
    about escalate() itself should move it further."""
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    result = rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    assert result["session"]["status"] == "WAITING_FOR_NURSE_ACK"

    # Re-fetching later (simulating time passing with nobody acking) still
    # shows WAITING_FOR_NURSE_ACK -- no background process advances it.
    still_waiting = rounding_service.get_session(session["id"])
    assert still_waiting["status"] == "WAITING_FOR_NURSE_ACK"


def test_cannot_escalate_twice_from_the_same_session(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    # Session is now WAITING_FOR_NURSE_ACK, not NEED_CLASSIFIED -- a second
    # escalate() call must be rejected, not silently create a duplicate.
    with pytest.raises(ConflictError):
        rounding_service.escalate(
            session["id"], summary="s2", priority="HIGH", route="NURSE_NOTIFICATION"
        )


def test_cannot_require_delivery_after_already_escalated(robot_storage):
    session = rounding_service.start_rounding("203")
    _to_interaction_started(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    rounding_service.escalate(
        session["id"], summary="s", priority="HIGH", route="NURSE_NOTIFICATION"
    )
    with pytest.raises(ConflictError):
        rounding_service.require_delivery(session["id"], "toileting")
