"""Tests for backend.services.workflow_service.

PR3 ("Task resource model") rewrite: every call now takes an explicit
request_id instead of operating on an implicit single global slot. See
that module's docstring for the concurrency rule and the `_view()` join.
"""
from datetime import datetime

import pytest

from backend.core.errors import ConflictError, DomainError, ForbiddenError
from backend.db import repositories
from backend.services import workflow_service


def test_create_request_ok(robot_storage):
    result = workflow_service.create_request("toileting")
    assert result["robot_state"] == "REQUEST_RECEIVED"
    assert result["kit"] == "KIT_TOILETING_A"
    # Item 5: _view() now exposes robot_id, defaulting to DEFAULT_ROBOT_ID
    # for a caller that didn't ask for a specific robot.
    assert result["robot_id"] == workflow_service.DEFAULT_ROBOT_ID


def test_create_request_assigns_to_given_robot_id(robot_storage):
    """Item 5: create_request(robot_id=...) actually assigns the task to
    that robot, not always DEFAULT_ROBOT_ID -- the service-layer half of
    the multi-robot support the DB/data model already had via the partial
    unique index (see test_concurrency_guard_is_per_robot_not_global)."""
    result = workflow_service.create_request("toileting", robot_id="ROBOT_2")
    assert result["robot_id"] == "ROBOT_2"
    assert repositories.get_active_task_for_robot("ROBOT_2") is not None
    assert repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID) is None


def test_create_request_concurrency_guard_is_scoped_per_robot_id(robot_storage):
    """Two different robot_ids can each hold an active task at the same
    time via create_request() itself (not just via a direct repositories.*
    call, as test_concurrency_guard_is_per_robot_not_global demonstrates)."""
    workflow_service.create_request("toileting", robot_id="ROBOT_1")
    result = workflow_service.create_request("water", robot_id="ROBOT_2")
    assert result["robot_state"] == "REQUEST_RECEIVED"

    with pytest.raises(ConflictError, match="in progress"):
        workflow_service.create_request("toileting", robot_id="ROBOT_1")


def test_get_current_state_is_scoped_to_given_robot_id(robot_storage):
    assert workflow_service.get_current_state("ROBOT_2")["robot_state"] == "IDLE"

    workflow_service.create_request("toileting", robot_id="ROBOT_2")

    assert workflow_service.get_current_state("ROBOT_2")["robot_state"] == "REQUEST_RECEIVED"
    assert workflow_service.get_current_state(workflow_service.DEFAULT_ROBOT_ID)["robot_state"] == "IDLE"


def test_create_request_while_in_progress(robot_storage):
    workflow_service.create_request("toileting")
    with pytest.raises(ConflictError, match="in progress"):
        workflow_service.create_request("water")


def test_cancel_from_request_received(robot_storage):
    result = workflow_service.create_request("toileting")
    assert workflow_service.cancel_request(result["request_id"])["robot_state"] == "IDLE"


def test_cancel_from_kit_selected(robot_storage):
    result = workflow_service.create_request("toileting")
    workflow_service.advance_state(result["request_id"], "KIT_SELECTED")
    assert workflow_service.cancel_request(result["request_id"])["robot_state"] == "IDLE"


def test_cancel_from_moving_fails(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    with pytest.raises(DomainError, match="Cannot cancel"):
        workflow_service.cancel_request(request_id)


def test_verify_ids_ok(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)
    verify_result = workflow_service.verify_ids(request_id, "PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert verify_result["ok"] is True


def test_verify_ids_fail(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)
    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "PATIENT_B_ROOM_204", "KIT_TOILETING_A")


def test_kit_released_without_nurse_confirmation_raises_forbidden(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE"]:
        workflow_service.advance_state(request_id, s)
    with pytest.raises(ForbiddenError):
        workflow_service.advance_state(request_id, "KIT_RELEASED")


def test_full_flow_completes_and_updates_request_status(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)
    workflow_service.verify_ids(request_id, "PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    workflow_service.advance_state(request_id, "TRAY_LIFTING")
    workflow_service.advance_state(request_id, "WAITING_FOR_NURSE_CONFIRMATION")
    workflow_service.advance_state(request_id, "KIT_RELEASED")
    final = workflow_service.advance_state(request_id, "COMPLETED")
    assert final["robot_state"] == "COMPLETED"
    assert repositories.get_care_request(request_id)["status"] == "COMPLETED"


def test_request_still_retrievable_after_cancel(robot_storage):
    """Unlike the old JSON singleton (which wiped the whole slot on
    cancel/reset), a cancelled request's history stays queryable by id."""
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.cancel_request(request_id)
    view = workflow_service.get_request(request_id)
    assert view is not None
    assert view["robot_state"] == "IDLE"
    assert repositories.get_care_request(request_id)["status"] == "CANCELLED"


def test_concurrency_guard_is_per_robot_not_global(robot_storage):
    """Regression test: the "another request in progress" guard must be
    scoped to a robot_id, not a hardcoded global flag. Two different
    robot_ids should each be able to hold one active task at the same
    time -- proving the constraint isn't secretly a global singleton in
    disguise."""
    result = workflow_service.create_request("toileting")
    assert result["robot_state"] == "REQUEST_RECEIVED"

    # A second robot has no active task of its own, so it is free.
    assert repositories.get_active_task_for_robot("ROBOT_2") is None

    # Simulate a second robot picking up a second request directly at the
    # repository level (workflow_service itself only ever assigns to
    # DEFAULT_ROBOT_ID today -- this test demonstrates the *data model*
    # already supports more than one robot without any schema change).
    repositories.insert_care_request(
        {
            "id": "req-2",
            "patient_id": "PATIENT_B_ROOM_204",
            "request_type": "water",
            "priority": "なし",
            "status": "ASSIGNED",
            "created_at": datetime(2026, 7, 8, 0, 0, 0),
            "completed_at": None,
        }
    )
    repositories.insert_robot_task(
        {
            "id": "task-2",
            "request_id": "req-2",
            "robot_id": "ROBOT_2",
            "state": "REQUEST_RECEIVED",
            "kit_id": "KIT_WATER",
            "assigned_at": datetime(2026, 7, 8, 0, 0, 0),
            "updated_at": datetime(2026, 7, 8, 0, 0, 0),
        }
    )

    assert repositories.get_active_task_for_robot("ROBOT_2") is not None
    # The first robot's task is unaffected by the second robot's task.
    assert repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID) is not None


# ---------------------------------------------------------------------------
# Escalation safety net: every path that forces a task into ERROR should
# also raise a nurse_escalations row (see workflow_service.
# _raise_error_escalation()), so a nurse working the Escalations queue sees
# it without having to separately watch the delivery task list for ERROR.
# ---------------------------------------------------------------------------


def _pending_error_escalations() -> list:
    return [
        e
        for e in repositories.list_nurse_escalations(status="PENDING")
        if e["source"] == "delivery_error"
    ]


def test_verify_ids_patient_mismatch_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "PATIENT_B_ROOM_204", "KIT_TOILETING_A")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["request_id"] == request_id
    assert escalations[0]["priority"] == "URGENT"
    assert escalations[0]["rounding_session_id"] is None
    assert "patient_id mismatch" in escalations[0]["reason"]


def test_verify_ids_kit_mismatch_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "PATIENT_A_ROOM_203", "KIT_WATER")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert "kit_id mismatch" in escalations[0]["reason"]


def test_kit_released_without_confirmation_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(ForbiddenError):
        workflow_service.advance_state(request_id, "KIT_RELEASED")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["request_id"] == request_id
    assert escalations[0]["priority"] == "URGENT"


def test_emergency_stop_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")

    workflow_service.emergency_stop(request_id)

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["patient_id"] == "PATIENT_A_ROOM_203"
    assert escalations[0]["priority"] == "URGENT"
    assert "Emergency stop" in escalations[0]["reason"]

