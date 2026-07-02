import sys
import uuid
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.config import REQUEST_TYPES, DEFAULT_PATIENT_ID
from robot_control.state_machine import ALLOWED_TRANSITIONS
from robot_control.logger import append_log, EventType
from vision.qr_detection.verify_patient_kit import verify
from backend.storage import load_state, save_state, append_log_entry


def create_request(request_type: str, patient_id: str = DEFAULT_PATIENT_ID) -> dict:
    state = load_state()
    if state.get("robot_state") not in ["IDLE", "COMPLETED", "ERROR"]:
        raise ValueError("Another request is in progress")
    info = REQUEST_TYPES.get(request_type)
    if not info:
        raise ValueError(f"Unknown request_type: {request_type}")
    new_state = {
        "request_id":  str(uuid.uuid4())[:8],
        "request":     info["label"],
        "kit":         info["kit"],
        "risk":        info["risk"],
        "patient_id":  patient_id,
        "robot_state": "REQUEST_RECEIVED",
        "timestamp":   datetime.now().isoformat(),
    }
    save_state(new_state)
    append_log(EventType.REQUEST_CREATED, patient_id=patient_id,
        request=info["label"], kit=info["kit"],
        next_state="REQUEST_RECEIVED", message=f"{request_type} request created")
    return new_state


def advance_state(next_state: str) -> dict:
    state = load_state()
    current = state.get("robot_state", "IDLE")
    allowed = ALLOWED_TRANSITIONS.get(current)
    if next_state == "KIT_RELEASED" and current != "WAITING_FOR_NURSE_CONFIRMATION":
        state["robot_state"] = "ERROR"
        save_state(state)
        append_log(EventType.ERROR, patient_id=state.get("patient_id", "-"),
            previous_state=current, next_state="ERROR",
            message="KIT_RELEASED attempted without nurse confirmation")
        raise ValueError("Nurse confirmation required before KIT_RELEASED")
    if allowed != next_state:
        state["robot_state"] = "ERROR"
        save_state(state)
        append_log(EventType.ERROR, patient_id=state.get("patient_id", "-"),
            previous_state=current, next_state="ERROR",
            message=f"Invalid transition {current} -> {next_state}")
        raise ValueError(f"Invalid transition: {current} -> {next_state}")
    prev = current
    state["robot_state"] = next_state
    save_state(state)
    append_log(EventType.STATE_TRANSITION, patient_id=state.get("patient_id", "-"),
        previous_state=prev, next_state=next_state)
    return state


def verify_ids(patient_id: str, kit_id: str) -> dict:
    state = load_state()
    if state.get("robot_state") != "VERIFYING_PATIENT":
        raise ValueError("Not in VERIFYING_PATIENT state")
    if patient_id != state.get("patient_id"):
        state["robot_state"] = "ERROR"
        save_state(state)
        append_log(EventType.QR_NG, patient_id=patient_id,
            previous_state="VERIFYING_PATIENT", next_state="ERROR",
            message="patient_id mismatch")
        raise ValueError("patient_id mismatch")
    if kit_id != state.get("kit"):
        state["robot_state"] = "ERROR"
        save_state(state)
        append_log(EventType.QR_NG, patient_id=patient_id,
            previous_state="VERIFYING_PATIENT", next_state="ERROR",
            message="kit_id mismatch")
        raise ValueError("kit_id mismatch")
    result = verify(patient_id, kit_id)
    if result["ok"]:
        state["robot_state"] = "DOCKING"
        save_state(state)
        append_log(EventType.QR_OK, patient_id=patient_id,
            previous_state="VERIFYING_PATIENT", next_state="DOCKING",
            message=result["message"])
        return {"ok": True, "state": state}
    else:
        state["robot_state"] = "ERROR"
        save_state(state)
        append_log(EventType.QR_NG, patient_id=patient_id,
            previous_state="VERIFYING_PATIENT", next_state="ERROR",
            message=result["message"])
        raise ValueError(result["message"])


def emergency_stop() -> dict:
    state = load_state()
    prev = state.get("robot_state", "IDLE")
    state["robot_state"] = "ERROR"
    save_state(state)
    append_log(EventType.EMERGENCY_STOP, patient_id=state.get("patient_id", "-"),
        previous_state=prev, next_state="ERROR", message="Emergency stop triggered")
    return state


def reset() -> dict:
    state = load_state()
    prev = state.get("robot_state", "ERROR")
    new_state = {"request": None, "robot_state": "IDLE"}
    save_state(new_state)
    append_log(EventType.RESET, patient_id=state.get("patient_id", "-"),
        previous_state=prev, next_state="IDLE", message="Reset to IDLE")
    return new_state


CANCELLABLE_STATES = {"REQUEST_RECEIVED", "KIT_SELECTED"}

def cancel_request() -> dict:
    state = load_state()
    prev = state.get("robot_state", "IDLE")
    if prev not in CANCELLABLE_STATES:
        raise ValueError(f"Cannot cancel from state: {prev}")
    new_state = {"request": None, "robot_state": "IDLE"}
    save_state(new_state)
    append_log(EventType.CANCEL, patient_id=state.get("patient_id", "-"),
        previous_state=prev, next_state="IDLE", message="Request cancelled")
    return new_state


def get_current_state() -> dict:
    return load_state()
