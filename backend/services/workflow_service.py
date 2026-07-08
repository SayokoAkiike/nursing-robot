"""Care-request / robot-task workflow orchestration.

PR3 ("Task resource model") rewrite. PR1/PR2 kept a single implicit
"current state" dict backed first by a JSON file, then by a singleton
`care_requests` row. This module now operates on real, independently
addressable rows: `care_requests` (the patient's request) and
`robot_tasks` (the robot's execution of it), joined by `request_id`.

To avoid a breaking API/UI change, every public function here still
returns the same dict shape callers have always gotten --
`{request_id, request_type, request, kit, risk, patient_id, robot_state,
timestamp}` -- via `_view()`, which joins the two tables and re-derives the
display label/kit/risk from `REQUEST_TYPES` rather than storing them
redundantly.

Concurrency rule: `create_request` raises ConflictError if
`repositories.get_active_task_for_robot(DEFAULT_ROBOT_ID)` returns a task
-- i.e. at most one non-terminal task per robot. This is the exact rule the
old JSON singleton enforced (see `backend/db/repositories.py`'s
NON_BLOCKING_TASK_STATES docstring), just expressed per `robot_id` instead
of as an unconditional global. `tests/test_workflow_service.py::
test_concurrency_guard_is_per_robot_not_global` is the regression test
proving this is no longer a hardcoded singleton.

Unlike the JSON/singleton versions, cancelling or resetting a request does
not erase it: `get_request(request_id)` keeps working for old request_ids
after their task has gone terminal, which is strictly more useful for a
real audit trail.
"""
import uuid
from datetime import datetime

from backend.core.config import DEFAULT_PATIENT_ID, REQUEST_TYPES
from backend.core.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from backend.db import repositories
from backend.services import verification_service
from backend.services.robot_service import allowed_next_state, verify_transition

DEFAULT_ROBOT_ID = "ROBOT_1"
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
        "request_id": fields.get("request_id"),
        "task_id": fields.get("task_id"),
        "patient_id": fields.get("patient_id", "—"),
        "request": fields.get("request", "—"),
        "kit": fields.get("kit", "—"),
        "previous_state": fields.get("previous_state", "—"),
        "next_state": fields.get("next_state", "—"),
        "result": fields.get("result", "—"),
        "message": fields.get("message", ""),
    }
    repositories.append_log_entry(entry)


def _record_transition(
    *,
    task_id: str,
    request_id: str,
    from_state: str | None,
    to_state: str,
    trigger_type: str,
    triggered_by: str | None = None,
    reason: str | None = None,
) -> None:
    """PR8: structured counterpart to `_log()`.

    `_log()` writes the human-readable robot_events row the nurse
    dashboard's log view already shows; this writes the same fact (a state
    changed) as a `task_state_transitions` row meant for querying/
    aggregation (PR11's /analytics/state-durations) rather than display.
    Called alongside `_log()`, never instead of it.
    """
    repositories.insert_task_state_transition(
        {
            "task_id": task_id,
            "request_id": request_id,
            "from_state": from_state,
            "to_state": to_state,
            "trigger_type": trigger_type,
            "triggered_by": triggered_by,
            "reason": reason,
            "occurred_at": datetime.now().isoformat(),
        }
    )


def _view(request_id: str) -> dict | None:
    """Join care_requests + robot_tasks into the legacy dict shape."""
    req = repositories.get_care_request(request_id)
    task = repositories.get_task_by_request_id(request_id)
    if req is None or task is None:
        return None
    info = REQUEST_TYPES.get(req["request_type"], {})
    return {
        "request_id": req["id"],
        "request_type": req["request_type"],
        "request": info.get("label", req["request_type"]),
        "kit": task["kit_id"],
        "risk": req["priority"],
        "patient_id": req["patient_id"],
        "robot_state": task["state"],
        "timestamp": req["created_at"],
    }


def _idle_view() -> dict:
    return {"request": None, "robot_state": "IDLE"}


def get_current_state() -> dict:
    """GET /state: the active task on the default robot, if any."""
    active = repositories.get_active_task_for_robot(DEFAULT_ROBOT_ID)
    if active is None:
        return _idle_view()
    return _view(active["request_id"]) or _idle_view()


def list_requests() -> list:
    """GET /requests: every task not in HIDDEN_FROM_LIST_STATES (mirrors the
    old singleton, which showed everything except IDLE -- including
    COMPLETED/ERROR tasks a nurse still needs to see)."""
    return [_view(t["request_id"]) for t in repositories.list_active_tasks()]


def get_request(request_id: str):
    return _view_or_error(request_id)


def require_request(request_id: str) -> dict:
    view = _view(request_id)
    if view is None:
        raise NotFoundError("Request not found")
    return view


def _require_task(request_id: str) -> dict:
    task = repositories.get_task_by_request_id(request_id)
    if task is None:
        raise NotFoundError("Request not found")
    return task
def _require_care_request(request_id: str) -> dict:
    req = repositories.get_care_request(request_id)
    if req is None:
        raise NotFoundError("Request not found")
    return req
def _view_or_error(request_id: str) -> dict:
    """Like `_view`, but raises instead of returning None.

    Used at call sites that have already confirmed (via `_require_task` /
    `_require_care_request`) that both rows exist, so `_view` returning
    None here would indicate a genuine invariant violation rather than a
    normal not-found case -- this makes that assumption explicit instead
    of silently propagating an Optional.
    """
    view = _view(request_id)
    if view is None:
        raise NotFoundError("Request not found")
    return view


def create_request(request_type: str, patient_id: str = DEFAULT_PATIENT_ID) -> dict:
    if repositories.get_active_task_for_robot(DEFAULT_ROBOT_ID) is not None:
        raise ConflictError("Another request is in progress")
    info = REQUEST_TYPES.get(request_type)
    if not info:
        raise DomainError(f"Unknown request_type: {request_type}")

    request_id = str(uuid.uuid4())[:8]
    task_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    repositories.insert_care_request(
        {
            "id": request_id,
            "patient_id": patient_id,
            "request_type": request_type,
            "priority": info["risk"],
            "status": "ASSIGNED",
            "created_at": now,
            "completed_at": None,
        }
    )
    repositories.insert_robot_task(
        {
            "id": task_id,
            "request_id": request_id,
            "robot_id": DEFAULT_ROBOT_ID,
            "state": "REQUEST_RECEIVED",
            "kit_id": info["kit"],
            "assigned_at": now,
            "updated_at": now,
        }
    )
    _log(
        EventType.REQUEST_CREATED,
        request_id=request_id,
        task_id=task_id,
        patient_id=patient_id,
        request=info["label"],
        kit=info["kit"],
        next_state="REQUEST_RECEIVED",
        message=f"{request_type} request created",
    )
    _record_transition(
        task_id=task_id,
        request_id=request_id,
        from_state=None,
        to_state="REQUEST_RECEIVED",
        trigger_type="request_created",
        triggered_by="patient",
    )
    return _view_or_error(request_id)


def advance_state(request_id: str, next_state: str) -> dict:
    task = _require_task(request_id)
    current = task["state"]
    now = datetime.now().isoformat()

    if next_state == "KIT_RELEASED" and current != "WAITING_FOR_NURSE_CONFIRMATION":
        repositories.update_task_state(task["id"], "ERROR", now)
        _log(
            EventType.ERROR,
            request_id=request_id,
            task_id=task["id"],
            previous_state=current,
            next_state="ERROR",
            message="KIT_RELEASED attempted without nurse confirmation",
        )
        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state=current,
            to_state="ERROR",
            trigger_type="manual_transition",
            triggered_by="nurse_token",
            reason="KIT_RELEASED attempted without nurse confirmation",
        )
        raise ForbiddenError("Nurse confirmation required before KIT_RELEASED")

    if allowed_next_state(current) != next_state:
        repositories.update_task_state(task["id"], "ERROR", now)
        _log(
            EventType.ERROR,
            request_id=request_id,
            task_id=task["id"],
            previous_state=current,
            next_state="ERROR",
            message=f"Invalid transition {current} -> {next_state}",
        )
        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state=current,
            to_state="ERROR",
            trigger_type="manual_transition",
            triggered_by="nurse_token",
            reason=f"Invalid transition {current} -> {next_state}",
        )
        raise DomainError(f"Invalid transition: {current} -> {next_state}")

    repositories.update_task_state(task["id"], next_state, now)
    _log(
        EventType.STATE_TRANSITION,
        request_id=request_id,
        task_id=task["id"],
        previous_state=current,
        next_state=next_state,
    )
    _record_transition(
        task_id=task["id"],
        request_id=request_id,
        from_state=current,
        to_state=next_state,
        trigger_type="nurse_confirmation"
        if (next_state == "KIT_RELEASED" and current == "WAITING_FOR_NURSE_CONFIRMATION")
        else "manual_transition",
        triggered_by="nurse_token",
    )
    if next_state == "COMPLETED":
        repositories.update_care_request_status(request_id, "COMPLETED", completed_at=now)
    return _view_or_error(request_id)


def verify_ids(request_id: str, patient_id: str, kit_id: str) -> dict:
    task = _require_task(request_id)
    req = _require_care_request(request_id)
    current = task["state"]
    now = datetime.now().isoformat()

    target = verify_transition(current)
    if target is None:
        raise ConflictError("Not in VERIFYING_PATIENT state")

    if patient_id != req.get("patient_id"):
        repositories.update_task_state(task["id"], "ERROR", now)
        repositories.insert_kit_verification(
            {
                "task_id": task["id"],
                "patient_id": patient_id,
                "kit_id": kit_id,
                "expected_patient_id": req.get("patient_id"),
                "scanned_patient_id": patient_id,
                "expected_kit_id": task.get("kit_id"),
                "scanned_kit_id": kit_id,
                "result": "NG",
                "message": "patient_id mismatch",
                "created_at": now,
            }
        )
        _log(
            EventType.QR_NG,
            request_id=request_id,
            task_id=task["id"],
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state="ERROR",
            message="patient_id mismatch",
        )
        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="patient_id mismatch",
        )
        raise DomainError("patient_id mismatch")

    if kit_id != task.get("kit_id"):
        repositories.update_task_state(task["id"], "ERROR", now)
        repositories.insert_kit_verification(
            {
                "task_id": task["id"],
                "patient_id": patient_id,
                "kit_id": kit_id,
                "expected_patient_id": req.get("patient_id"),
                "scanned_patient_id": patient_id,
                "expected_kit_id": task.get("kit_id"),
                "scanned_kit_id": kit_id,
                "result": "NG",
                "message": "kit_id mismatch",
                "created_at": now,
            }
        )
        _log(
            EventType.QR_NG,
            request_id=request_id,
            task_id=task["id"],
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state="ERROR",
            message="kit_id mismatch",
        )
        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="kit_id mismatch",
        )
        raise DomainError("kit_id mismatch")

    result = verification_service.verify(patient_id, kit_id)
    repositories.insert_kit_verification(
        {
            "task_id": task["id"],
            "patient_id": patient_id,
            "kit_id": kit_id,
            "expected_patient_id": req.get("patient_id"),
            "scanned_patient_id": patient_id,
            "expected_kit_id": task.get("kit_id"),
            "scanned_kit_id": kit_id,
            "result": "OK" if result["ok"] else "NG",
            "message": result["message"],
            "created_at": now,
        }
    )
    if result["ok"]:
        repositories.update_task_state(task["id"], target, now)
        _log(
            EventType.QR_OK,
            request_id=request_id,
            task_id=task["id"],
            patient_id=patient_id,
            previous_state="VERIFYING_PATIENT",
            next_state=target,
            message=result["message"],
        )
        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state=target,
            trigger_type="verification",
            triggered_by="verification_service",
        )
        return {"ok": True, "state": _view_or_error(request_id)}

    repositories.update_task_state(task["id"], "ERROR", now)
    _log(
        EventType.QR_NG,
        request_id=request_id,
        task_id=task["id"],
        patient_id=patient_id,
        previous_state="VERIFYING_PATIENT",
        next_state="ERROR",
        message=result["message"],
    )
    _record_transition(
        task_id=task["id"],
        request_id=request_id,
        from_state="VERIFYING_PATIENT",
        to_state="ERROR",
        trigger_type="verification",
        triggered_by="verification_service",
        reason=result["message"],
    )
    raise DomainError(result["message"])


def emergency_stop(request_id: str) -> dict:
    task = _require_task(request_id)
    now = datetime.now().isoformat()
    prev = task["state"]
    repositories.update_task_state(task["id"], "ERROR", now)
    _log(
        EventType.EMERGENCY_STOP,
        request_id=request_id,
        task_id=task["id"],
        previous_state=prev,
        next_state="ERROR",
        message="Emergency stop triggered",
    )
    _record_transition(
        task_id=task["id"],
        request_id=request_id,
        from_state=prev,
        to_state="ERROR",
        trigger_type="emergency_stop",
        triggered_by="nurse_token",
    )
    return _view_or_error(request_id)


def reset(request_id: str) -> dict:
    task = _require_task(request_id)
    now = datetime.now().isoformat()
    prev = task["state"]
    repositories.update_task_state(task["id"], "IDLE", now)
    repositories.update_care_request_status(request_id, "CANCELLED", completed_at=now)
    _log(
        EventType.RESET,
        request_id=request_id,
        task_id=task["id"],
        previous_state=prev,
        next_state="IDLE",
        message="Reset to IDLE",
    )
    _record_transition(
        task_id=task["id"],
        request_id=request_id,
        from_state=prev,
        to_state="IDLE",
        trigger_type="reset",
        triggered_by="nurse_token",
    )
    return _view_or_error(request_id)


def cancel_request(request_id: str, actor: str = "patient") -> dict:
    task = _require_task(request_id)
    now = datetime.now().isoformat()
    prev = task["state"]
    if prev not in CANCELLABLE_STATES:
        raise DomainError(f"Cannot cancel from state: {prev}")
    repositories.update_task_state(task["id"], "IDLE", now)
    repositories.update_care_request_status(request_id, "CANCELLED", completed_at=now)
    _log(
        EventType.CANCEL,
        request_id=request_id,
        task_id=task["id"],
        previous_state=prev,
        next_state="IDLE",
        message="Request cancelled",
    )
    _record_transition(
        task_id=task["id"],
        request_id=request_id,
        from_state=prev,
        to_state="IDLE",
        trigger_type="patient_cancel" if actor == "patient" else "nurse_cancel",
        triggered_by="patient" if actor == "patient" else "nurse_token",
    )
    return _view_or_error(request_id)
