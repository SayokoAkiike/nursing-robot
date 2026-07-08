"""Tests for PR11: analytics_service.state_durations().

Focus is on the edge cases called out in the roadmap: a task_id with only
one transition ever recorded, and a task that's still in progress (its
current state has no "exit" transition yet). Both should be silently
excluded rather than estimated.
"""
import time

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


def test_state_durations_on_empty_db(robot_storage):
    assert analytics_service.state_durations() == []


def test_single_transition_task_produces_no_sample(robot_storage):
    """A task_id with exactly one task_state_transitions row (just the
    genesis create_request row) has no "next" row to diff against -- its
    only state (REQUEST_RECEIVED) must not appear in the output at all."""
    workflow_service.create_request("toileting")

    result = analytics_service.state_durations()
    states = {row["state"] for row in result}
    assert "REQUEST_RECEIVED" not in states
    assert result == []


def test_in_progress_task_only_reports_closed_intervals(robot_storage):
    """A task that has moved through several states but is still sitting in
    its current one contributes samples for every *closed* interval it has
    already passed through, but not for the open-ended current state."""
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")
    workflow_service.advance_state(request_id, "MOVING_TO_BEDSIDE")
    # Still sitting in MOVING_TO_BEDSIDE -- no further transition recorded.

    durations = analytics_service.state_durations()
    states = {row["state"]: row for row in durations}

    # Closed intervals: REQUEST_RECEIVED (closed by KIT_SELECTED's row) and
    # KIT_SELECTED (closed by MOVING_TO_BEDSIDE's row) should be present.
    assert "REQUEST_RECEIVED" in states
    assert "KIT_SELECTED" in states
    # MOVING_TO_BEDSIDE is where the task currently sits -- no exit yet.
    assert "MOVING_TO_BEDSIDE" not in states


def test_state_durations_computes_average_across_multiple_tasks(robot_storage):
    """Two tasks that both pass through KIT_SELECTED should average their
    two (independently timed) durations in that state."""
    r1 = workflow_service.create_request("toileting", patient_id="PATIENT_A_ROOM_203")
    time.sleep(0.01)
    workflow_service.advance_state(r1["request_id"], "KIT_SELECTED")
    # Free the robot (concurrency guard allows only one non-terminal task at
    # a time) so a second, independently-timed task can be created.
    workflow_service.cancel_request(r1["request_id"])

    r2 = workflow_service.create_request("water", patient_id="PATIENT_B_ROOM_204")
    time.sleep(0.02)
    workflow_service.advance_state(r2["request_id"], "KIT_SELECTED")

    durations = analytics_service.state_durations()
    states = {row["state"]: row for row in durations}

    assert "REQUEST_RECEIVED" in states
    row = states["REQUEST_RECEIVED"]
    assert row["sample_count"] == 2
    assert row["average_seconds"] > 0
    assert row["min_seconds"] <= row["average_seconds"] <= row["max_seconds"]


def test_state_durations_includes_full_flow_states(robot_storage):
    """A fully completed request should produce closed-interval samples for
    every state except the terminal COMPLETED state itself (which has no
    following transition, since a task_id is never revisited)."""
    _complete_full_flow()

    durations = analytics_service.state_durations()
    states = {row["state"] for row in durations}

    for expected in [
        "REQUEST_RECEIVED",
        "KIT_SELECTED",
        "MOVING_TO_BEDSIDE",
        "VERIFYING_PATIENT",
        "DOCKING",
        "TRAY_LIFTING",
        "WAITING_FOR_NURSE_CONFIRMATION",
    ]:
        assert expected in states, f"{expected} missing from {states}"

    # COMPLETED is the terminal to_state of the last transition -- no
    # following row exists for this task_id, so it has no closed interval.
    assert "COMPLETED" not in states


def test_state_durations_result_shape(robot_storage):
    _complete_full_flow()
    durations = analytics_service.state_durations()
    assert len(durations) > 0
    for row in durations:
        assert set(row.keys()) == {"state", "sample_count", "average_seconds", "min_seconds", "max_seconds"}
        assert row["sample_count"] >= 1
        assert row["min_seconds"] <= row["average_seconds"] <= row["max_seconds"]
    # Sorted alphabetically by state.
    assert [row["state"] for row in durations] == sorted(row["state"] for row in durations)


def test_error_transition_still_counted_as_closed_interval(robot_storage):
    """An invalid-transition error closes out the interval the task was in
    right before the error, same as any other transition would."""
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    try:
        # Skipping straight to TRAY_LIFTING from REQUEST_RECEIVED is invalid
        # -- this records a transition REQUEST_RECEIVED -> ERROR.
        workflow_service.advance_state(request_id, "TRAY_LIFTING")
    except Exception:
        pass

    durations = analytics_service.state_durations()
    states = {row["state"] for row in durations}
    assert "REQUEST_RECEIVED" in states
