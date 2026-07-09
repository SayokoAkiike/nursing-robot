"""Tests for backend.services.escalation_service."""
import pytest

from backend.core.errors import ConflictError, NotFoundError
from backend.services import escalation_service, rounding_service


def _escalated_session():
    session = rounding_service.start_rounding("203")
    rounding_service.detect_patient(session["id"], "PATIENT_A_ROOM_203")
    rounding_service.start_interaction(session["id"])
    rounding_service.classify_need(session["id"], "トイレに行きたいです")
    result = rounding_service.escalate(
        session["id"],
        summary="203号室 Patient A がトイレ介助を希望。単独離床リスクあり。",
        priority="HIGH",
        suggested_action="看護師が訪室して介助してください。",
        route="NURSE_NOTIFICATION",
    )
    return session, result["escalation_id"]


def test_get_escalation_missing_raises_not_found(robot_storage):
    with pytest.raises(NotFoundError):
        escalation_service.get_escalation("does-not-exist")


def test_acknowledge_marks_escalation_acknowledged(robot_storage):
    _session, escalation_id = _escalated_session()

    result = escalation_service.acknowledge(escalation_id, "nurse_demo")
    assert result["escalation"]["status"] == "ACKNOWLEDGED"
    assert result["escalation"]["acknowledged_by"] == "nurse_demo"
    assert result["escalation"]["acknowledged_at"] is not None


def test_acknowledge_also_completes_the_rounding_session(robot_storage):
    session, escalation_id = _escalated_session()

    result = escalation_service.acknowledge(escalation_id, "nurse_demo")
    assert result["session"]["id"] == session["id"]
    assert result["session"]["status"] == "COMPLETED"


def test_acknowledge_twice_raises_conflict(robot_storage):
    _session, escalation_id = _escalated_session()
    escalation_service.acknowledge(escalation_id, "nurse_demo")

    with pytest.raises(ConflictError):
        escalation_service.acknowledge(escalation_id, "nurse_demo_2")


def test_list_escalations_filters_by_status(robot_storage):
    _session1, esc1 = _escalated_session()
    _session2, esc2 = _escalated_session()
    escalation_service.acknowledge(esc1, "nurse_demo")

    pending = escalation_service.list_escalations(status="PENDING")
    assert [e["id"] for e in pending] == [esc2]

    acked = escalation_service.list_escalations(status="ACKNOWLEDGED")
    assert [e["id"] for e in acked] == [esc1]


def test_list_escalations_for_dashboard_sorts_pending_first(robot_storage):
    _session1, esc1 = _escalated_session()
    _session2, esc2 = _escalated_session()
    # Acknowledge the first-created one, leaving the second PENDING.
    escalation_service.acknowledge(esc1, "nurse_demo")

    ordered = escalation_service.list_escalations_for_dashboard()
    assert ordered[0]["id"] == esc2
    assert ordered[0]["status"] == "PENDING"
    assert ordered[1]["id"] == esc1
    assert ordered[1]["status"] == "ACKNOWLEDGED"
