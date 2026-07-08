"""Tests for backend.services.robot_service.

Rewritten against the single ALLOWED_TRANSITIONS-based ruleset (see that
module's docstring). The previous version of this file tested
`RobotStateMachine`'s now-removed `NORMAL_FLOW`-index-based logic, which
diverged from production in a safety-relevant way: it allowed a *generic*
transition straight from VERIFYING_PATIENT to DOCKING, silently bypassing QR
verification. `test_verifying_to_docking_requires_verification` below is the
regression test for that fix.
"""
from backend.services.robot_service import (
    ALLOWED_TRANSITIONS,
    RobotState,
    RobotStateMachine,
    is_valid_transition,
    verify_transition,
)

FULL_FLOW = [
    RobotState.KIT_SELECTED.value,
    RobotState.MOVING_TO_BEDSIDE.value,
    RobotState.VERIFYING_PATIENT.value,
]


def _to_waiting_for_nurse(robot: RobotStateMachine) -> None:
    robot.receive_request()
    for s in FULL_FLOW:
        robot.transition(s)
    robot.simulate_verification()
    robot.transition(RobotState.TRAY_LIFTING.value)
    robot.transition(RobotState.WAITING_FOR_NURSE_CONFIRMATION.value)


def test_normal_flow():
    robot = RobotStateMachine()
    assert robot.state == RobotState.IDLE.value
    robot.receive_request()
    robot.transition(RobotState.KIT_SELECTED.value)
    assert robot.state == RobotState.KIT_SELECTED.value


def test_invalid_transition_goes_to_error():
    robot = RobotStateMachine()
    robot.receive_request()
    robot.transition(RobotState.COMPLETED.value)
    assert robot.state == RobotState.ERROR.value


def test_emergency_stop():
    robot = RobotStateMachine()
    robot.receive_request()
    robot.emergency_stop()
    assert robot.state == RobotState.ERROR.value


def test_reset_from_error():
    robot = RobotStateMachine()
    robot.emergency_stop()
    robot.reset()
    assert robot.state == RobotState.IDLE.value


def test_cannot_release_kit_without_nurse():
    robot = RobotStateMachine()
    _to_waiting_for_nurse(robot)
    result = robot.transition(RobotState.COMPLETED.value)  # wrong target on purpose
    assert result is False
    assert robot.state == RobotState.ERROR.value


def test_kit_released_requires_nurse_confirmation():
    robot = RobotStateMachine()
    _to_waiting_for_nurse(robot)
    result = robot.transition(RobotState.KIT_RELEASED.value)
    assert result is True
    assert robot.state == RobotState.KIT_RELEASED.value


def test_cannot_skip_to_kit_released():
    robot = RobotStateMachine()
    robot.receive_request()
    result = robot.transition(RobotState.KIT_RELEASED.value)
    assert result is False
    assert robot.state == RobotState.ERROR.value


def test_error_only_allows_reset_to_idle():
    robot = RobotStateMachine()
    robot.emergency_stop()
    robot.transition(RobotState.COMPLETED.value)
    assert robot.state == RobotState.ERROR.value
    robot.reset()
    assert robot.state == RobotState.IDLE.value


def test_allowed_transitions_no_verifying_to_docking():
    assert "VERIFYING_PATIENT" not in ALLOWED_TRANSITIONS


def test_verifying_to_docking_requires_verification():
    """Regression test: a *generic* transition into DOCKING from
    VERIFYING_PATIENT must fail -- only `simulate_verification()`
    (production: `verification_service.verify_ids`) may make that move."""
    robot = RobotStateMachine()
    robot.receive_request()
    robot.transition(RobotState.KIT_SELECTED.value)
    robot.transition(RobotState.MOVING_TO_BEDSIDE.value)
    robot.transition(RobotState.VERIFYING_PATIENT.value)

    assert is_valid_transition(RobotState.VERIFYING_PATIENT.value, RobotState.DOCKING.value) is False

    result = robot.transition(RobotState.DOCKING.value)
    assert result is False
    assert robot.state == RobotState.ERROR.value


def test_verify_transition_target():
    assert verify_transition(RobotState.VERIFYING_PATIENT.value) == RobotState.DOCKING.value
    assert verify_transition(RobotState.IDLE.value) is None

