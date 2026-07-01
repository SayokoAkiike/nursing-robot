import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision.qr_detection.verify_patient_kit import verify
from robot_control.state_machine import RobotStateMachine, RobotState


# ── verify_patient_kit のテスト ──────────────────────

def test_verify_ok_toileting():
    result = verify("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True

def test_verify_ng_wrong_kit():
    result = verify("PATIENT_A_ROOM_203", "ALERT_NURSE_ONLY")
    assert result["ok"] is False

def test_verify_ng_unknown_patient():
    result = verify("PATIENT_UNKNOWN", "KIT_WATER")
    assert result["ok"] is False

def test_verify_ok_water():
    result = verify("PATIENT_B_ROOM_204", "KIT_WATER")
    assert result["ok"] is True


# ── state_machine のテスト ───────────────────────────

def test_normal_flow():
    robot = RobotStateMachine()
    assert robot.state == RobotState.IDLE
    robot.transition(RobotState.REQUEST_RECEIVED)
    assert robot.state == RobotState.REQUEST_RECEIVED
    robot.transition(RobotState.KIT_SELECTED)
    assert robot.state == RobotState.KIT_SELECTED

def test_invalid_transition_goes_to_error():
    robot = RobotStateMachine()
    result = robot.transition(RobotState.COMPLETED)
    assert robot.state == RobotState.ERROR

def test_emergency_stop():
    robot = RobotStateMachine()
    robot.transition(RobotState.REQUEST_RECEIVED)
    robot.emergency_stop()
    assert robot.state == RobotState.ERROR

def test_reset_from_error():
    robot = RobotStateMachine()
    robot.emergency_stop()
    assert robot.state == RobotState.ERROR
    robot.reset()
    assert robot.state == RobotState.IDLE

def test_cannot_release_kit_without_nurse():
    robot = RobotStateMachine()
    for s in [
        RobotState.REQUEST_RECEIVED,
        RobotState.KIT_SELECTED,
        RobotState.MOVING_TO_BEDSIDE,
        RobotState.VERIFYING_PATIENT,
        RobotState.DOCKING,
        RobotState.TRAY_LIFTING,
        RobotState.WAITING_FOR_NURSE_CONFIRMATION,
    ]:
        robot.transition(s)
    assert robot.state == RobotState.WAITING_FOR_NURSE_CONFIRMATION
    result = robot.transition(RobotState.COMPLETED)
    assert result is False
    assert robot.state == RobotState.ERROR


# ── 追加テスト ────────────────────────────────────────────

def test_kit_released_requires_nurse_confirmation():
    robot = RobotStateMachine()
    # WAITING_FOR_NURSE_CONFIRMATION まで進める
    for s in [
        RobotState.REQUEST_RECEIVED,
        RobotState.KIT_SELECTED,
        RobotState.MOVING_TO_BEDSIDE,
        RobotState.VERIFYING_PATIENT,
        RobotState.DOCKING,
        RobotState.TRAY_LIFTING,
        RobotState.WAITING_FOR_NURSE_CONFIRMATION,
    ]:
        robot.transition(s)
    # 看護師確認後は KIT_RELEASED に進める
    result = robot.transition(RobotState.KIT_RELEASED)
    assert result is True
    assert robot.state == RobotState.KIT_RELEASED

def test_cannot_skip_to_kit_released():
    robot = RobotStateMachine()
    robot.transition(RobotState.REQUEST_RECEIVED)
    # WAITING_FOR_NURSE_CONFIRMATION を経ずに KIT_RELEASED は ERROR になる
    result = robot.transition(RobotState.KIT_RELEASED)
    assert result is False
    assert robot.state == RobotState.ERROR

def test_error_only_allows_reset_to_idle():
    robot = RobotStateMachine()
    robot.emergency_stop()
    assert robot.state == RobotState.ERROR
    # ERROR から COMPLETED には進めない
    result = robot.transition(RobotState.COMPLETED)
    assert result is False
    # ERROR から IDLE へのリセットはできる
    robot.reset()
    assert robot.state == RobotState.IDLE

def test_qr_ng_result():
    from vision.qr_detection.verify_patient_kit import verify
    result = verify("PATIENT_A_ROOM_203", "ALERT_NURSE_ONLY")
    assert result["ok"] is False

def test_qr_ok_result():
    from vision.qr_detection.verify_patient_kit import verify
    result = verify("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True
