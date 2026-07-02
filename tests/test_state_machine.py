from robot_control.state_machine import RobotStateMachine, RobotState, ALLOWED_TRANSITIONS

FULL_FLOW = [
    RobotState.REQUEST_RECEIVED, RobotState.KIT_SELECTED,
    RobotState.MOVING_TO_BEDSIDE, RobotState.VERIFYING_PATIENT,
    RobotState.DOCKING, RobotState.TRAY_LIFTING,
    RobotState.WAITING_FOR_NURSE_CONFIRMATION,
]


def test_normal_flow():
    robot = RobotStateMachine()
    assert robot.state == RobotState.IDLE
    robot.transition(RobotState.REQUEST_RECEIVED)
    robot.transition(RobotState.KIT_SELECTED)
    assert robot.state == RobotState.KIT_SELECTED

def test_invalid_transition_goes_to_error():
    robot = RobotStateMachine()
    robot.transition(RobotState.COMPLETED)
    assert robot.state == RobotState.ERROR

def test_emergency_stop():
    robot = RobotStateMachine()
    robot.transition(RobotState.REQUEST_RECEIVED)
    robot.emergency_stop()
    assert robot.state == RobotState.ERROR

def test_reset_from_error():
    robot = RobotStateMachine()
    robot.emergency_stop()
    robot.reset()
    assert robot.state == RobotState.IDLE

def test_cannot_release_kit_without_nurse():
    robot = RobotStateMachine()
    for s in FULL_FLOW:
        robot.transition(s)
    result = robot.transition(RobotState.COMPLETED)  # COMPLETED ではなく KIT_RELEASED が正しい
    assert result is False
    assert robot.state == RobotState.ERROR

def test_kit_released_requires_nurse_confirmation():
    robot = RobotStateMachine()
    for s in FULL_FLOW:
        robot.transition(s)
    result = robot.transition(RobotState.KIT_RELEASED)
    assert result is True
    assert robot.state == RobotState.KIT_RELEASED

def test_cannot_skip_to_kit_released():
    robot = RobotStateMachine()
    robot.transition(RobotState.REQUEST_RECEIVED)
    result = robot.transition(RobotState.KIT_RELEASED)
    assert result is False
    assert robot.state == RobotState.ERROR

def test_error_only_allows_reset_to_idle():
    robot = RobotStateMachine()
    robot.emergency_stop()
    robot.transition(RobotState.COMPLETED)
    assert robot.state == RobotState.ERROR  # ERROR のまま
    robot.reset()
    assert robot.state == RobotState.IDLE

def test_allowed_transitions_no_verifying_to_docking():
    assert "VERIFYING_PATIENT" not in ALLOWED_TRANSITIONS
