"""Tests for PR12: backend/scripts/seed_demo_data.py and reset_demo_data.py,
plus the repositories.py helpers they're built on
(shift_timestamps_for_request / delete_all_data).
"""
from datetime import datetime, timedelta

import pytest

from backend.db import repositories
from backend.scripts import reset_demo_data, seed_demo_data
from backend.services import workflow_service


def test_shift_timestamps_for_request_shifts_every_related_row(robot_storage):
    result = workflow_service.create_request("toileting", patient_id="PATIENT_A_ROOM_203")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")

    before = repositories.get_care_request(request_id)
    before_created_at = datetime.fromisoformat(before["created_at"])

    delta_seconds = -3600  # one hour into the past
    repositories.shift_timestamps_for_request(request_id, delta_seconds)

    after = repositories.get_care_request(request_id)
    after_created_at = datetime.fromisoformat(after["created_at"])
    assert after_created_at == before_created_at - timedelta(seconds=3600)

    task = repositories.get_task_by_request_id(request_id)
    transitions = repositories.list_task_state_transitions(request_id=request_id)
    assert len(transitions) == 2
    for row in transitions:
        occurred_at = datetime.fromisoformat(row["occurred_at"])
        # Both shifted by the same delta -- the gap between them (the
        # REQUEST_RECEIVED duration) must be unchanged.
        assert occurred_at < datetime.now()
    gap = datetime.fromisoformat(transitions[1]["occurred_at"]) - datetime.fromisoformat(
        transitions[0]["occurred_at"]
    )
    assert gap.total_seconds() >= 0

    logs = repositories.load_logs()
    assert len(logs) >= 1
    for entry in logs:
        # robot_events uses "%Y-%m-%d %H:%M:%S" (space-separated, no "T").
        parsed = datetime.strptime(entry["timestamp"], "%Y-%m-%d %H:%M:%S")
        assert parsed < datetime.now()

    assert task is not None  # sanity: request/task still linked after the shift


def test_shift_timestamps_leaves_null_completed_at_alone(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    repositories.shift_timestamps_for_request(request_id, -100)
    row = repositories.get_care_request(request_id)
    assert row["completed_at"] is None


def test_delete_all_data_wipes_every_table(robot_storage):
    workflow_service.create_request("toileting")
    assert repositories.list_all_care_requests() != []
    assert repositories.list_all_robot_tasks() != []

    repositories.delete_all_data()

    assert repositories.list_all_care_requests() == []
    assert repositories.list_all_robot_tasks() == []
    assert repositories.list_all_kit_verifications() == []
    assert repositories.list_task_state_transitions() == []
    assert repositories.load_logs() == []


def test_seed_generates_requested_number_of_tasks(robot_storage):
    created = seed_demo_data.seed(days=7, tasks=5, long_wait_seconds=0.01, seed_value=42)
    assert len(created) == 5
    assert repositories.list_all_care_requests().__len__() == 5
    for _request_id, scenario in created:
        assert scenario in seed_demo_data.SCENARIOS


def test_seed_spreads_created_at_within_requested_window(robot_storage):
    days = 3
    created = seed_demo_data.seed(days=days, tasks=6, long_wait_seconds=0.01, seed_value=7)
    now = datetime.now()
    window_start = now - timedelta(days=days, seconds=5)  # small tolerance for test runtime
    for request_id, _scenario in created:
        row = repositories.get_care_request(request_id)
        created_at = datetime.fromisoformat(row["created_at"])
        assert window_start <= created_at <= now + timedelta(seconds=5)


def test_seed_refuses_when_robot_is_active(robot_storage):
    result = workflow_service.create_request("toileting")
    workflow_service.advance_state(result["request_id"], "KIT_SELECTED")
    # Task is now in KIT_SELECTED -- an active, non-terminal state -- so the
    # robot is occupied. seed() must refuse rather than raise a confusing
    # ConflictError mid-run from workflow_service.create_request.
    with pytest.raises(RuntimeError, match="active on the default robot"):
        seed_demo_data.seed(days=1, tasks=3, long_wait_seconds=0.01)


def test_seed_never_leaves_robot_blocked_between_scenarios(robot_storage):
    """Every scenario must end in a NON_BLOCKING_TASK_STATES state so the
    next scenario's create_request() doesn't hit the concurrency guard."""
    # If this raises ConflictError, some scenario left the robot occupied.
    seed_demo_data.seed(days=1, tasks=10, long_wait_seconds=0.01, seed_value=123)


def test_reset_wipes_data_generated_by_seed(robot_storage):
    seed_demo_data.seed(days=1, tasks=3, long_wait_seconds=0.01, seed_value=1)
    assert repositories.list_all_care_requests() != []

    reset_demo_data.reset()

    assert repositories.list_all_care_requests() == []


def test_reset_refuses_when_robot_is_active(robot_storage):
    result = workflow_service.create_request("toileting")
    workflow_service.advance_state(result["request_id"], "KIT_SELECTED")
    with pytest.raises(RuntimeError, match="active on the default robot"):
        reset_demo_data.reset()
    # And the data must still be there -- the refusal happens before any delete.
    assert repositories.list_all_care_requests() != []


def test_seed_scenarios_all_end_in_non_blocking_state(robot_storage):
    """Directly checks the invariant test_seed_never_leaves_robot_blocked_
    between_scenarios relies on: after seeding, the robot must be free."""
    seed_demo_data.seed(days=1, tasks=15, long_wait_seconds=0.01, seed_value=99)
    assert repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID) is None
