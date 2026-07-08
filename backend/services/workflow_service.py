"""Care-request / robot-task workflow orchestration.
 
Moved from `robot_control/service.py`. Behavioural changes from the
original:
  - Transition validity is delegated entirely to
    `backend.services.robot_service` (single source of truth; see that
    module's docstring for why the old class-based state machine and this
    dict-based one used to disagree).
  - Raises typed errors from `backend.core.errors` instead of bare
    `ValueError`, so route handlers no longer need to pattern-match error
    messages to pick an HTTP status code.
"""
import uuid
from datetime import datetime
 
from backend.core.config import DEFAULT_PATIENT_ID, REQUEST_TYPES
from backend.core.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from backend.db import repositories
from backend.services import verification_service
from backend.services.robot_service import allowed_next_state, verify_transition
 
CANCELLABLE_STATES = {"REQUEST_RECEIVED", "KIT_SELECTED"}
 
 
class EventType:
    REQUEST_CREATED = "REQUEST_CREATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    QR_OK = "QR_OK"
    QR_NG = "QR_NG"
    CANCEL = "CANCEL"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    ERROR = "ERROR"
    RESET = "RESET"
    COMPLETED = "COMPLETED"
 
 
def _log(event_type: str, **fields) -> None:
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "patient_id": fields.get("patient_id", "—"),
        "request": fields.get("request", "—"),
        "kit": fields.get("kit", "—"),
        "previous_state": fields.get("previous_state", "—"),
        "next_state": fields.get("next_state", "—"),
        "result": fields.get("result", "—"),
        "message": fields.get("message", ""),
    }
    repositories.append_log_entry(entry)
 
 
def get_current_state() -> dict:
    return repositories.load_state()
 
 
def list_requests() -> list:
    return repositories.list_requests()
 
 
def get_request(request_id: str):
    return repositories.get_request(request_id)
 
 
def require_request(request_id: str) -> dict:
    req = repositories.get_request(request_id)
    if not req:
        raise NotFoundError("Request not found")
    return req
 
 
def create_request(request_type: str, patient_id: str = DEFAULT_PATIENT_ID) -> dict:
    state = repositories.load_state()
    if state.get("robot_state") not in ["IDLE", "COMPLETED", "ERROR"]:
        raise ConflictError("Another request is in progress")
    info = REQUEST_TYPES.get(request_type)
    if not info:
        raise DomainError(f"Unknown request_type: {request_type}")
    new_state = {
        "request_id": str(uuid.uuid4())[:8],
        "request": info["label"],
        "kit": info["kit"],
        "risk": info["risk"],
        "patient_id": patient_id,
        "robot_state": "REQUEST_RECEIVED",
        "timestamp": datetime.now().isoformat(),
    }
    repositories.save_state(new_state)
    _log(
        EventType.REQUEST_CREATED,
        patient_id=patient_id,
        request=info["label"],
        kit=info["kit"],
        next_state="REQUEST_RECEIVED",
        message=f"{request_type} request created",
    )
    return new_state
 
 
def advance_state(next_state: str) -> dict:
    state = repositories.load_state()
    current = state.get("robot_state", "IDLE")
 
    if next_state == "KIT_RELEASED" and current != "WAITING_FOR_NURSE_CONFIRMATION":
        state["robot_state"] = "ERROR"
        repositories.save_state(state)
        _log(
            EventType.ERROR,
            patient_id=state.get("patient_id", "-"),
            previous_state=current,
            next_state="ERROR",
            message="KIT_RELEASED attempted without nurse confirmation",
        )
        raise ForbiddenError("Nurse confirmation required before KIT_RELEASED")
 
    if allowed_next_state(current) != next_state:
        state["robot_state"] = "ERROR"
        repositories.save_state(state)
        _log(
            EventType.ERROR,
            patient_id=state.get("patient_id", "-"),
            previous_state=current,
            next_state="ERROR",
            message=f"Invalid transition {current} -> {next_state}",
        )
        raise DomainError(f"Invalid transition: {current} -> {next_state}")
 
    state["robot_state"] = next_state
    repositories.save_state(state)
    _log(
        EventType.STATE_TRANSITION,
        patient_id=state.get("patient_id", "-"),
        previous_state=current,
        next_state=next_state,
    )
    return state
 
 
def verify_ids(patient_id: str, kit_id: str) -> dict:
    state = repositories.load_state()
    current = state.get("robot_state")
 
    target = verify_transition(current)
    if target is None:
        raise ConflictError("Not in VERIFYING_PATIENT state")
 
    if patient_id != state.get("patient_id"):
        state["robot_state"] = "ERROR"
        repositories.save_state(state)
        _log(
            EventType.QR_NG,
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state="ERROR",
            message="patient_id mismatch",
        )
        raise DomainError("patient_id mismatch")
 
    if kit_id != state.get("kit"):
        state["robot_state"] = "ERROR"
        repositories.save_state(state)
        _log(
            EventType.QR_NG,
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state="ERROR",
            message="kit_id mismatch",
        )
        raise DomainError("kit_id mismatch")
 
    result = verification_service.verify(patient_id, kit_id)
    if result["ok"]:
        state["robot_state"] = target
        repositories.save_state(state)
        _log(
            EventType.QR_OK,
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state=target,
            message=result["message"],
        )
        return {"ok": True, "state": state}
 
    state["robot_state"] = "ERROR"
    repositories.save_state(state)
    _log(
        EventType.QR_NG,
        patient_id=patient_id,
        previous_state="VERIFYING_PATIENT",
        next_state="ERROR",
        message=result["message"],
    )
    raise DomainError(result["message"])
 
 
def emergency_stop() -> dict:
    state = repositories.load_state()
    prev = state.get("robot_state", "IDLE")
    state["robot_state"] = "ERROR"
    repositories.save_state(state)
    _log(
        EventType.EMERGENCY_STOP,
        patient_id=state.get("patient_id", "-"),
        previous_state=prev,
        next_state="ERROR",
        message="Emergency stop triggered",
    )
    return state
 
 
def reset() -> dict:
    state = repositories.load_state()
    prev = state.get("robot_state", "ERROR")
    new_state = {"request": None, "robot_state": "IDLE"}
    repositories.save_state(new_state)
    _log(
        EventType.RESET,
        patient_id=state.get("patient_id", "-"),
        previous_state=prev,
        next_state="IDLE",
        message="Reset to IDLE",
    )
    return new_state
 
 
def cancel_request() -> dict:
    state = repositories.load_state()
    prev = state.get("robot_state", "IDLE")
    if prev not in CANCELLABLE_STATES:
        raise DomainError(f"Cannot cancel from state: {prev}")
    new_state = {"request": None, "robot_state": "IDLE"}
    repositories.save_state(new_state)
    _log(
        EventType.CANCEL,
        patient_id=state.get("patient_id", "-"),
        previous_state=prev,
        next_state="IDLE",
        message="Request cancelled",
    )
    return new_state
 
