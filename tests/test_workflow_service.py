"""Tests for backend.services.workflow_service (moved from
robot_control/service.py -- see backend/services/workflow_service.py's
docstring)."""
import pytest
 
from backend.core.errors import ConflictError, DomainError, ForbiddenError
from backend.services import workflow_service
 
 
def test_create_request_ok(robot_storage):
    result = workflow_service.create_request("toileting")
    assert result["robot_state"] == "REQUEST_RECEIVED"
    assert result["kit"] == "KIT_TOILETING_A"
 
 
def test_create_request_while_in_progress(robot_storage):
    workflow_service.create_request("toileting")
    with pytest.raises(ConflictError, match="in progress"):
        workflow_service.create_request("water")
 
 
def test_cancel_from_request_received(robot_storage):
    workflow_service.create_request("toileting")
    assert workflow_service.cancel_request()["robot_state"] == "IDLE"
 
 
def test_cancel_from_kit_selected(robot_storage):
    workflow_service.create_request("toileting")
    workflow_service.advance_state("KIT_SELECTED")
    assert workflow_service.cancel_request()["robot_state"] == "IDLE"
 
 
def test_cancel_from_moving_fails(robot_storage):
    workflow_service.create_request("toileting")
    workflow_service.advance_state("KIT_SELECTED")
    workflow_service.advance_state("MOVING_TO_BEDSIDE")
    with pytest.raises(DomainError, match="Cannot cancel"):
        workflow_service.cancel_request()
 
 
def test_verify_ids_ok(robot_storage):
    workflow_service.create_request("toileting")
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(s)
    result = workflow_service.verify_ids("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True
 
 
def test_verify_ids_fail(robot_storage):
    workflow_service.create_request("toileting")
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(s)
    with pytest.raises(DomainError):
        workflow_service.verify_ids("PATIENT_B_ROOM_204", "KIT_TOILETING_A")
 
 
def test_kit_released_without_nurse_confirmation_raises_forbidden(robot_storage):
    workflow_service.create_request("toileting")
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE"]:
        workflow_service.advance_state(s)
    with pytest.raises(ForbiddenError):
        workflow_service.advance_state("KIT_RELEASED")
 
