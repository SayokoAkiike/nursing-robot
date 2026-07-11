"""Tests for backend.services.escalation_service."""
from datetime import datetime, timedelta

import pytest

from backend.core.errors import ConflictError, NotFoundError
from backend.db import repositories
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


# ---------------------------------------------------------------------------
# check_and_escalate_overdue() / the escalation-timeout safety net.
# ---------------------------------------------------------------------------


def _insert_escalation(
    escalation_id: str, priority: str, created_at: "datetime", status: str = "PENDING"
) -> None:
    repositories.insert_nurse_escalation(
        {
            "id": escalation_id,
            "rounding_session_id": None,
            "request_id": None,
            "patient_id": "PATIENT_A_ROOM_203",
            "room": "203",
            "summary": "test escalation",
            "priority": priority,
            "reason": None,
            "suggested_action": None,
            "status": status,
            "created_at": created_at,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "source": "rounding",
        }
    )


def test_check_and_escalate_overdue_bumps_priority_past_timeout(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-overdue", "HIGH", created_at)
    now = created_at + timedelta(seconds=301)  # HIGH's timeout is 300s

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert [e["id"] for e in bumped] == ["esc-overdue"]
    escalation = escalation_service.get_escalation("esc-overdue")
    assert escalation["priority"] == "URGENT"
    assert escalation["escalated_count"] == 1
    assert escalation["last_escalated_at"] == now


def test_check_and_escalate_overdue_leaves_recent_escalations_alone(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-recent", "HIGH", created_at)
    now = created_at + timedelta(seconds=100)  # well under HIGH's 300s timeout

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    escalation = escalation_service.get_escalation("esc-recent")
    assert escalation["priority"] == "HIGH"
    assert escalation["escalated_count"] == 0


def test_check_and_escalate_overdue_ignores_acknowledged_escalations(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-acked", "HIGH", created_at, status="ACKNOWLEDGED")
    now = created_at + timedelta(hours=1)

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    assert escalation_service.get_escalation("esc-acked")["priority"] == "HIGH"


def test_check_and_escalate_overdue_urgent_stays_urgent(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-urgent", "URGENT", created_at)
    now = created_at + timedelta(hours=1)

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    escalation = escalation_service.get_escalation("esc-urgent")
    assert escalation["priority"] == "URGENT"
    assert escalation["escalated_count"] == 0


def test_list_escalations_for_dashboard_triggers_overdue_bump(robot_storage):
    old_created_at = datetime.now() - timedelta(hours=1)
    _insert_escalation("esc-stale", "MEDIUM", old_created_at)

    ordered = escalation_service.list_escalations_for_dashboard()

    stale = next(e for e in ordered if e["id"] == "esc-stale")
    assert stale["priority"] == "HIGH"
    assert stale["escalated_count"] == 1


# ---------------------------------------------------------------------------
# acknowledge() against an escalation with no rounding session (raised by
# workflow_service._raise_error_escalation() instead of rounding_service).
# ---------------------------------------------------------------------------


def test_acknowledge_without_rounding_session_returns_none_session(robot_storage):
    repositories.insert_nurse_escalation(
        {
            "id": "esc-delivery-error",
            "rounding_session_id": None,
            "request_id": "req-123",
            "patient_id": "PATIENT_A_ROOM_203",
            "room": "203",
            "summary": "QR mismatch",
            "priority": "URGENT",
            "reason": "patient_id mismatch",
            "suggested_action": None,
            "status": "PENDING",
            "created_at": datetime.now(),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "source": "delivery_error",
        }
    )

    result = escalation_service.acknowledge("esc-delivery-error", "nurse_demo")

    assert result["session"] is None
    assert result["escalation"]["status"] == "ACKNOWLEDGED"


# ---- PR30: raise_direct_escalation (vision/pose source) --------------------


def test_raise_direct_escalation_creates_pending_row_with_no_session(robot_storage):
    escalation = escalation_service.raise_direct_escalation(
        room="203",
        patient_id="PATIENT_A_ROOM_203",
        summary="203号室 PATIENT_A_ROOM_203 が離床（転倒の危険）を検知されました。",
        priority="URGENT",
        reason="fall_risk",
        suggested_action="至急、看護師が訪室し、患者の安全を直接確認してください。転倒・転落の恐れがあります。",
        source="vision_pose",
    )
    assert escalation["status"] == "PENDING"
    assert escalation["rounding_session_id"] is None
    assert escalation["request_id"] is None
    assert escalation["source"] == "vision_pose"
    assert escalation["priority"] == "URGENT"


def test_raise_direct_escalation_is_immediately_listed(robot_storage):
    escalation_service.raise_direct_escalation(
        room="203",
        patient_id="PATIENT_A_ROOM_203",
        summary="s",
        priority="URGENT",
        reason="fall_risk",
        suggested_action=None,
        source="vision_pose",
    )
    pending = escalation_service.list_escalations(status="PENDING")
    assert len(pending) == 1
    assert pending[0]["source"] == "vision_pose"


def test_raise_direct_escalation_can_be_acknowledged_with_no_session_to_complete(robot_storage):
    escalation = escalation_service.raise_direct_escalation(
        room="203",
        patient_id="PATIENT_A_ROOM_203",
        summary="s",
        priority="URGENT",
        reason="fall_risk",
        suggested_action=None,
        source="vision_pose",
    )
    result = escalation_service.acknowledge(escalation["id"], "nurse_demo")
    assert result["session"] is None
    assert result["escalation"]["status"] == "ACKNOWLEDGED"
