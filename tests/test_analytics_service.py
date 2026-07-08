"""Tests for PR10: analytics_service (summary / verification-failures).

Tests the service layer directly (like test_evaluate_detector.py does for
its module), rather than only through the API, since the aggregation logic
itself is what's worth covering here.
"""
from backend.services import analytics_service, workflow_service


def _advance_to_verifying_patient(request_id):
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    return workflow_service.advance_state(request_id, "VERIFYING_PATIENT")


def _complete_full_flow(patient_id="PATIENT_A_ROOM_203", request_type="toileting", kit_id="KIT_TOILETING_A"):
    result = workflow_service.create_request(request_type, patient_id=patient_id)
    request_id = result["request_id"]
    _advance_to_verifying_patient(request_id)
    workflow_service.verify_ids(request_id, patient_id, kit_id)
    workflow_service.advance_state(request_id, "TRAY_LIFTING")
    workflow_service.advance_state(request_id, "WAITING_FOR_NURSE_CONFIRMATION")
    workflow_service.advance_state(request_id, "KIT_RELEASED")
    workflow_service.advance_state(request_id, "COMPLETED")
    return request_id


def test_summary_on_empty_db(robot_storage):
    result = analytics_service.summary()
    assert result == {
        "total_requests": 0,
        "completed_requests": 0,
        "cancelled_requests": 0,
        "error_tasks": 0,
        "verification_attempts": 0,
        "verification_failure_rate": 0.0,
        "average_completion_seconds": None,
    }


def test_verification_failures_on_empty_db(robot_storage):
    assert analytics_service.verification_failures() == []


def test_summary_counts_completed_and_cancelled_requests(robot_storage):
    _complete_full_flow(patient_id="PATIENT_A_ROOM_203")

    cancelled = workflow_service.create_request("water", patient_id="PATIENT_B_ROOM_204")
    workflow_service.cancel_request(cancelled["request_id"])

    result = analytics_service.summary()
    assert result["total_requests"] == 2
    assert result["completed_requests"] == 1
    assert result["cancelled_requests"] == 1


def test_summary_counts_error_tasks(robot_storage):
    result = workflow_service.create_request("toileting")
    workflow_service.emergency_stop(result["request_id"])

    summary = analytics_service.summary()
    assert summary["error_tasks"] == 1


def test_summary_computes_average_completion_seconds(robot_storage):
    _complete_full_flow()

    result = analytics_service.summary()
    assert result["average_completion_seconds"] is not None
    assert result["average_completion_seconds"] >= 0


def test_summary_verification_failure_rate(robot_storage):
    _complete_full_flow(patient_id="PATIENT_A_ROOM_203")

    bad = workflow_service.create_request("water", patient_id="PATIENT_B_ROOM_204")
    request_id = bad["request_id"]
    _advance_to_verifying_patient(request_id)
    try:
        workflow_service.verify_ids(request_id, "WRONG_PATIENT", "KIT_WATER")
    except Exception:
        pass

    result = analytics_service.summary()
    assert result["verification_attempts"] == 2
    assert result["verification_failure_rate"] == 0.5


def test_verification_failures_groups_by_message(robot_storage):
    patient_mismatch = workflow_service.create_request("toileting", patient_id="PATIENT_A_ROOM_203")
    request_id = patient_mismatch["request_id"]
    _advance_to_verifying_patient(request_id)
    try:
        workflow_service.verify_ids(request_id, "WRONG_PATIENT", "KIT_TOILETING_A")
    except Exception:
        pass

    kit_mismatch = workflow_service.create_request("water", patient_id="PATIENT_B_ROOM_204")
    request_id2 = kit_mismatch["request_id"]
    _advance_to_verifying_patient(request_id2)
    try:
        workflow_service.verify_ids(request_id2, "PATIENT_B_ROOM_204", "KIT_TOILETING_A")
    except Exception:
        pass

    result = analytics_service.verification_failures()
    failure_types = {row["failure_type"]: row["count"] for row in result}
    assert failure_types.get("patient_id mismatch") == 1
    assert failure_types.get("kit_id mismatch") == 1
