import pytest
from robot_control import service


def test_create_request_ok(robot_storage):
    result = service.create_request("toileting")
    assert result["robot_state"] == "REQUEST_RECEIVED"
    assert result["kit"] == "KIT_TOILETING_A"

def test_create_request_while_in_progress(robot_storage):
    service.create_request("toileting")
    with pytest.raises(ValueError, match="in progress"):
        service.create_request("water")

def test_cancel_from_request_received(robot_storage):
    service.create_request("toileting")
    assert service.cancel_request()["robot_state"] == "IDLE"

def test_cancel_from_kit_selected(robot_storage):
    service.create_request("toileting")
    service.advance_state("KIT_SELECTED")
    assert service.cancel_request()["robot_state"] == "IDLE"

def test_cancel_from_moving_fails(robot_storage):
    service.create_request("toileting")
    service.advance_state("KIT_SELECTED")
    service.advance_state("MOVING_TO_BEDSIDE")
    with pytest.raises(ValueError, match="Cannot cancel"):
        service.cancel_request()

def test_verify_ids_ok(robot_storage):
    service.create_request("toileting")
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        service.advance_state(s)
    result = service.verify_ids("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True

def test_verify_ids_fail(robot_storage):
    service.create_request("toileting")
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        service.advance_state(s)
    with pytest.raises(ValueError):
        service.verify_ids("PATIENT_B_ROOM_204", "KIT_TOILETING_A")
