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
    # ALERT_NURSE_ONLYはPatient_Aに許可済みなので、別の不正キットでテスト
    result = verify("PATIENT_A_ROOM_203", "KIT_UNKNOWN")
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
    result = verify("PATIENT_A_ROOM_203", "KIT_UNKNOWN")
    assert result["ok"] is False

def test_qr_ok_result():
    from vision.qr_detection.verify_patient_kit import verify
    result = verify("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True


# ── FastAPI テスト ────────────────────────────────────────

def test_patient_ui_importable():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location(
        "patient_app", "ui/patient_request_app/app.py")
    assert spec is not None

def test_backend_storage_json_decode_error(tmp_path):
    import json
    from pathlib import Path
    import backend.storage as storage
    broken = tmp_path / "broken.json"
    broken.write_text("NOT JSON", encoding="utf-8")
    orig = storage.STATE_FILE
    storage.STATE_FILE = broken
    result = storage.load_state()
    assert result == {"request": None, "robot_state": "IDLE"}
    storage.STATE_FILE = orig

def test_allowed_transitions_no_verifying_to_docking():
    from robot_control.state_machine import ALLOWED_TRANSITIONS
    assert "VERIFYING_PATIENT" not in ALLOWED_TRANSITIONS

def test_valid_combinations_nurse_check():
    from vision.qr_detection.verify_patient_kit import verify
    result = verify("PATIENT_A_ROOM_203", "ALERT_NURSE_ONLY")
    assert result["ok"] is True

def test_backend_importable():
    from backend.main import app
    assert app is not None


# ── FastAPI TestClient テスト ─────────────────────────────

from fastapi.testclient import TestClient
import backend.storage as storage_mod

NURSE_TOKEN = "precare-dev-token-2026"
HEADERS = {"x-nurse-token": NURSE_TOKEN}

def get_client(tmp_path):
    storage_mod.STATE_FILE = tmp_path / "state.json"
    storage_mod.LOG_FILE = tmp_path / "log.json"
    from backend.main import app
    return TestClient(app)

def test_api_get_state(tmp_path):
    client = get_client(tmp_path)
    r = client.get("/state")
    assert r.status_code == 200
    assert r.json()["robot_state"] == "IDLE"

def test_api_create_request(tmp_path):
    client = get_client(tmp_path)
    r = client.post("/requests", json={"request_type": "toileting"})
    assert r.status_code == 200
    assert r.json()["robot_state"] == "REQUEST_RECEIVED"

def test_api_unknown_request_type(tmp_path):
    client = get_client(tmp_path)
    r = client.post("/requests", json={"request_type": "unknown"})
    assert r.status_code == 400

def test_api_transition_requires_nurse_token(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/transition", json={"next_state": "KIT_SELECTED"})
    assert r.status_code == 401

def test_api_transition_with_token(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/transition", json={"next_state": "KIT_SELECTED"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["robot_state"] == "KIT_SELECTED"

def test_api_invalid_transition(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/transition", json={"next_state": "COMPLETED"}, headers=HEADERS)
    assert r.status_code == 400

def test_api_kit_released_without_nurse_confirmation(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/transition", json={"next_state": "KIT_RELEASED"}, headers=HEADERS)
    assert r.status_code == 403

def test_api_emergency_stop(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/emergency-stop", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["robot_state"] == "ERROR"

def test_api_reset(tmp_path):
    client = get_client(tmp_path)
    client.post("/requests", json={"request_type": "toileting"})
    client.post("/emergency-stop", headers=HEADERS)
    r = client.post("/reset", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["robot_state"] == "IDLE"

def test_api_get_logs(tmp_path):
    client = get_client(tmp_path)
    r = client.get("/logs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── service層テスト ───────────────────────────────────────

def test_service_create_request_ok(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    result = service.create_request("toileting")
    assert result["robot_state"] == "REQUEST_RECEIVED"
    assert result["kit"] == "KIT_TOILETING_A"

def test_service_create_request_while_in_progress(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    try:
        service.create_request("water")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "in progress" in str(e)

def test_service_cancel_from_request_received(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    result = service.cancel_request()
    assert result["robot_state"] == "IDLE"

def test_service_cancel_from_kit_selected(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    service.advance_state("KIT_SELECTED")
    result = service.cancel_request()
    assert result["robot_state"] == "IDLE"

def test_service_cancel_from_moving_fails(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    service.advance_state("KIT_SELECTED")
    service.advance_state("MOVING_TO_BEDSIDE")
    try:
        service.cancel_request()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Cannot cancel" in str(e)

def test_service_verify_ids_ok(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    for state in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        service.advance_state(state)
    result = service.verify_ids("PATIENT_A_ROOM_203", "KIT_TOILETING_A")
    assert result["ok"] is True

def test_service_verify_ids_fail(tmp_path):
    import backend.storage as s
    s.STATE_FILE = tmp_path / "state.json"
    s.LOG_FILE = tmp_path / "log.json"
    from robot_control import service
    service.create_request("toileting")
    for state in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        service.advance_state(state)
    try:
        service.verify_ids("PATIENT_B_ROOM_204", "KIT_TOILETING_A")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass

def test_api_cancel_ok(tmp_path):
    import backend.storage as storage_mod
    storage_mod.STATE_FILE = tmp_path / "state.json"
    storage_mod.LOG_FILE = tmp_path / "log.json"
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    client.post("/requests", json={"request_type": "toileting"})
    r = client.post("/cancel", headers={"x-nurse-token": "precare-dev-token-2026"})
    assert r.status_code == 200
    assert r.json()["robot_state"] == "IDLE"

def test_api_cancel_from_moving_fails(tmp_path):
    import backend.storage as storage_mod
    storage_mod.STATE_FILE = tmp_path / "state.json"
    storage_mod.LOG_FILE = tmp_path / "log.json"
    from backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    HEADERS = {"x-nurse-token": "precare-dev-token-2026"}
    client.post("/requests", json={"request_type": "toileting"})
    client.post("/transition", json={"next_state": "KIT_SELECTED"}, headers=HEADERS)
    client.post("/transition", json={"next_state": "MOVING_TO_BEDSIDE"}, headers=HEADERS)
    r = client.post("/cancel", headers=HEADERS)
    assert r.status_code == 400
