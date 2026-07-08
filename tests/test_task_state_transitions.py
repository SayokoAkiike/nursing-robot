"""Tests for PR8: task_state_transitions audit trail.

Every place `workflow_service` changes a robot_tasks.state should also
write a task_state_transitions row via `_record_transition()`. These tests
check the recorded rows directly through
`repositories.list_task_state_transitions`, independent of the human-
readable `robot_events` log PR2 already covers.
"""
import pytest

from backend.core.errors import DomainError
from backend.db import repositories
from backend.services import workflow_service


def _advance_to_verifying_patient(request_id):
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    return workflow_service.advance_state(request_id, "VERIFYING_PATIENT")


def test_create_request_records_initial_transition(robot_storage):
    result = workflow_service.create_request("toileting")
    rows = repositories.list_task_state_transitions(request_id=result["request_id"])
    assert len(rows) == 1
    assert rows[0]["from_state"] is None
    assert rows[0]["to_state"] == "REQUEST_RECEIVED"
    assert rows[0]["trigger_type"] == "request_created"
    assert rows[0]["triggered_by"] == "patient"


def test_advance_state_records_manual_transition(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["from_state"] == "REQUEST_RECEIVED"
    assert rows[-1]["to_state"] == "KIT_SELECTED"
    assert rows[-1]["trigger_type"] == "manual_transition"
    assert rows[-1]["triggered_by"] == "nurse_token"


def test_invalid_transition_records_error_with_reason(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    with pytest.raises(DomainError):
        workflow_service.advance_state(request_id, "COMPLETED")
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["to_state"] == "ERROR"
    assert rows[-1]["trigger_type"] == "manual_transition"
    assert "Invalid transition" in rows[-1]["reason"]


def test_verify_ids_success_records_verification_trigger(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    workflow_service.verify_ids(request_id, result["patient_id"], "KIT_TOILETING_A")
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["from_state"] == "VERIFYING_PATIENT"
    assert rows[-1]["to_state"] == "DOCKING"
    assert rows[-1]["trigger_type"] == "verification"
    assert rows[-1]["triggered_by"] == "verification_service"


def test_verify_ids_mismatch_records_error_with_reason(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "WRONG_PATIENT", "KIT_TOILETING_A")
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["to_state"] == "ERROR"
    assert rows[-1]["trigger_type"] == "verification"
    assert rows[-1]["reason"] == "patient_id mismatch"


def test_nurse_confirmation_transition_has_dedicated_trigger_type(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    workflow_service.verify_ids(request_id, result["patient_id"], "KIT_TOILETING_A")
    workflow_service.advance_state(request_id, "TRAY_LIFTING")
    workflow_service.advance_state(request_id, "WAITING_FOR_NURSE_CONFIRMATION")
    workflow_service.advance_state(request_id, "KIT_RELEASED")
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["from_state"] == "WAITING_FOR_NURSE_CONFIRMATION"
    assert rows[-1]["to_state"] == "KIT_RELEASED"
    assert rows[-1]["trigger_type"] == "nurse_confirmation"
    assert rows[-1]["triggered_by"] == "nurse_token"


def test_emergency_stop_records_transition(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.emergency_stop(request_id)
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["to_state"] == "ERROR"
    assert rows[-1]["trigger_type"] == "emergency_stop"


def test_reset_records_transition(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.emergency_stop(request_id)
    workflow_service.reset(request_id)
    rows = repositories.list_task_state_transitions(request_id=request_id)
    assert rows[-1]["from_state"] == "ERROR"
    assert rows[-1]["to_state"] == "IDLE"
    assert rows[-1]["trigger_type"] == "reset"


def test_cancel_actor_determines_trigger_type(robot_storage):
    patient_result = workflow_service.create_request("toileting")
    workflow_service.cancel_request(patient_result["request_id"])
    patient_rows = repositories.list_task_state_transitions(request_id=patient_result["request_id"])
    assert patient_rows[-1]["trigger_type"] == "patient_cancel"
    assert patient_rows[-1]["triggered_by"] == "patient"

    nurse_result = workflow_service.create_request("water")
    workflow_service.cancel_request(nurse_result["request_id"], actor="nurse")
    nurse_rows = repositories.list_task_state_transitions(request_id=nurse_result["request_id"])
    assert nurse_rows[-1]["trigger_type"] == "nurse_cancel"
    assert nurse_rows[-1]["triggered_by"] == "nurse_token"


def test_list_task_state_transitions_filters_by_task_id(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    task = repositories.get_task_by_request_id(request_id)
    by_task = repositories.list_task_state_transitions(task_id=task["id"])
    by_request = repositories.list_task_state_transitions(request_id=request_id)
    assert by_task == by_request
    assert len(by_task) == 1
