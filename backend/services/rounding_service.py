"""Rounding / patient check-in workflow orchestration (PR23).

Mirrors `backend/services/workflow_service.py`'s shape (the delivery
workflow's orchestration module) deliberately, so the two read the same
way side by side:

  - `_log()` writes a human-readable `robot_events` row (same table
    `workflow_service` writes to -- `request_id`/`task_id` are both
    nullable there, so a rounding-only event with neither is fine; this
    also means the nurse dashboard's existing single log view picks up
    rounding activity for free once PR26 wires it in).
  - `_view()` / `_require_session()` return/raise on a rounding_sessions
    row the same way `_view()` / `_require_task()` do for a task.
  - Transitions along the linear spine go through
    `robot_service.is_valid_rounding_transition()`; the one branch point
    (NEED_CLASSIFIED) goes through `robot_service.rounding_branch_transition()`,
    exactly as `verify_transition()` is the one branch point in the
    delivery flow.

Unlike `workflow_service`, this module does not write a
`task_state_transitions`-equivalent audit table -- PR22's schema (matching
the proposal doc) defines only `rounding_sessions` /
`patient_interactions` / `nurse_escalations`, not a fourth transitions-log
table. `rounding_sessions.status` plus its `updated_at` timestamp is the
audit trail for now; a dedicated log table (mirroring how PR8 added
`task_state_transitions` well after PR3's initial task model) can follow
in a later PR if per-transition analytics are needed.
"""
import uuid
from datetime import datetime

from backend.core.errors import ConflictError, DomainError, NotFoundError
from backend.db import repositories
from backend.services import need_classification_service, workflow_service
from backend.services.robot_service import (
    is_valid_rounding_transition,
    rounding_branch_transition,
)

DEFAULT_ROBOT_ID = "ROBOT_1"

DEFAULT_PROMPT = "何かお困りですか？立ち上がらず、そのままお話しください。"


class RoundingEventType:
    ROUNDING_STARTED = "ROUNDING_STARTED"
    PATIENT_DETECTED = "PATIENT_DETECTED"
    INTERACTION_STARTED = "INTERACTION_STARTED"
    NEED_CLASSIFIED = "NEED_CLASSIFIED"
    INFORMATION_PROVIDED = "INFORMATION_PROVIDED"
    ESCALATED = "ESCALATED"
    DELIVERY_REQUESTED = "DELIVERY_REQUESTED"
    ROUNDING_COMPLETED = "ROUNDING_COMPLETED"


def _log(event_type: str, **fields) -> None:
    entry = {
        "timestamp": datetime.now(),
        "event_type": event_type,
        "request_id": fields.get("request_id"),
        "task_id": None,
        "patient_id": fields.get("patient_id", "—"),
        "request": fields.get("request", "—"),
        "kit": fields.get("kit", "—"),
        "previous_state": fields.get("previous_state", "—"),
        "next_state": fields.get("next_state", "—"),
        "result": fields.get("result", "—"),
        "message": fields.get("message", ""),
    }
    repositories.append_log_entry(entry)


def _require_session(session_id: str) -> dict:
    session = repositories.get_rounding_session(session_id)
    if session is None:
        raise NotFoundError("Rounding session not found")
    return session


def _view(session_id: str) -> dict:
    return _require_session(session_id)


def _advance(session_id: str, current: str, next_state: str) -> None:
    """Linear-spine transition guarded by ROUNDING_ALLOWED_TRANSITIONS.
    Raises ConflictError (not a silent no-op) on an illegal transition --
    same contract as workflow_service.advance_state()."""
    if not is_valid_rounding_transition(current, next_state):
        raise ConflictError(
            f"Cannot transition rounding session from {current} to {next_state}"
        )
    repositories.update_rounding_session(
        session_id, status=next_state, updated_at=datetime.now()
    )


def start_rounding(room: str, robot_id: str = DEFAULT_ROBOT_ID) -> dict:
    session_id = str(uuid.uuid4())[:8]
    now = datetime.now()
    repositories.insert_rounding_session(
        {
            "id": session_id,
            "robot_id": robot_id,
            "room": room,
            "patient_id": None,
            "status": "ROUNDING",
            "started_at": now,
            "ended_at": None,
            "interaction_summary": None,
            "detected_need": None,
            "escalation_level": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    _log(
        RoundingEventType.ROUNDING_STARTED,
        next_state="ROUNDING",
        message=f"Rounding started in room {room}",
    )
    return _view(session_id)


def detect_patient(session_id: str, patient_id: str) -> dict:
    session = _require_session(session_id)
    current = session["status"]
    _advance(session_id, current, "PATIENT_DETECTED")
    repositories.update_rounding_session(session_id, patient_id=patient_id)
    _log(
        RoundingEventType.PATIENT_DETECTED,
        patient_id=patient_id,
        previous_state=current,
        next_state="PATIENT_DETECTED",
    )
    return _view(session_id)


def start_interaction(session_id: str) -> dict:
    """PATIENT_DETECTED -> APPROACHING_BEDSIDE -> INTERACTION_STARTED in one
    call. There is no separate "approach" trigger in the proposed API
    surface (only /detect-patient and /start-interaction exist) -- the
    robot approaching the bedside is modeled as an internal part of
    beginning the interaction, not something a caller initiates on its
    own. Returns the prompt to show/speak to the patient alongside the
    updated session."""
    session = _require_session(session_id)
    current = session["status"]
    _advance(session_id, current, "APPROACHING_BEDSIDE")
    _advance(session_id, "APPROACHING_BEDSIDE", "INTERACTION_STARTED")
    _log(
        RoundingEventType.INTERACTION_STARTED,
        patient_id=session.get("patient_id"),
        previous_state=current,
        next_state="INTERACTION_STARTED",
    )
    return {"prompt": DEFAULT_PROMPT, "session": _view(session_id)}


def classify_need(
    session_id: str, patient_response: str, input_mode: str = "simulated"
) -> dict:
    """INTERACTION_STARTED -> NEED_CLASSIFIED (linear step), plus records
    the interaction and the classification result. Does *not* advance
    past NEED_CLASSIFIED -- that is left to whichever of
    provide_information() / escalate() / require_delivery() the returned
    `route` points to, mirroring how verify_ids() decides DOCKING vs ERROR
    but a *separate* caller decides what happens next on the delivery
    side too."""
    session = _require_session(session_id)
    current = session["status"]
    _advance(session_id, current, "NEED_CLASSIFIED")

    classification = need_classification_service.classify(patient_response)
    now = datetime.now()

    repositories.insert_patient_interaction(
        {
            "rounding_session_id": session_id,
            "patient_id": session.get("patient_id"),
            "room": session.get("room"),
            "prompt": DEFAULT_PROMPT,
            "patient_response": patient_response,
            "input_mode": input_mode,
            "detected_need": classification.detected_need,
            "confidence": classification.confidence,
            "created_at": now,
        }
    )
    repositories.update_rounding_session(
        session_id,
        detected_need=classification.detected_need,
        escalation_level=classification.escalation_level,
        updated_at=now,
    )
    _log(
        RoundingEventType.NEED_CLASSIFIED,
        patient_id=session.get("patient_id"),
        previous_state=current,
        next_state="NEED_CLASSIFIED",
        message=f"detected_need={classification.detected_need} route={classification.route}",
    )

    room = session.get("room")
    patient_id = session.get("patient_id")
    need_label = need_classification_service.need_label(classification.detected_need)
    summary = f"{room}号室 {patient_id} が「{need_label}」を訴えています。"

    return {
        "detected_need": classification.detected_need,
        "escalation_level": classification.escalation_level,
        "route": classification.route,
        "summary": summary,
        "suggested_action": need_classification_service.suggested_action(
            classification.detected_need
        ),
        "session": _view(session_id),
    }


def provide_information(session_id: str) -> dict:
    """The INFORMATION_ONLY branch out of NEED_CLASSIFIED: nothing to
    escalate, patient has been given an in-person response by the robot.
    NEED_CLASSIFIED -> INFORMATION_PROVIDED -> COMPLETED in one call."""
    session = _require_session(session_id)
    current = session["status"]
    target = rounding_branch_transition(current, "INFORMATION_ONLY")
    if target is None:
        raise ConflictError(f"Cannot provide information from state: {current}")
    repositories.update_rounding_session(
        session_id, status=target, updated_at=datetime.now()
    )
    _advance(session_id, target, "COMPLETED")
    repositories.update_rounding_session(session_id, ended_at=datetime.now())
    _log(
        RoundingEventType.ROUNDING_COMPLETED,
        patient_id=session.get("patient_id"),
        previous_state=current,
        next_state="COMPLETED",
        message="No nurse action needed",
    )
    return _view(session_id)


def escalate(
    session_id: str,
    summary: str,
    priority: str,
    suggested_action: str | None = None,
    reason: str | None = None,
    route: str = "NURSE_NOTIFICATION",
) -> dict:
    """The NURSE_NOTIFICATION / URGENT_ESCALATION branch out of
    NEED_CLASSIFIED: raises a `nurse_escalations` row and moves the
    session to WAITING_FOR_NURSE_ACK. `route` selects which of the two
    NEED_CLASSIFIED branches this is (both currently target
    ESCALATING_TO_NURSE -- see ROUNDING_BRANCH_TARGETS in
    robot_service.py); passing the wrong route for the session's actual
    classification is caller error, not something this function can
    detect from `summary`/`priority` alone, so it isn't re-validated here."""
    session = _require_session(session_id)
    current = session["status"]
    target = rounding_branch_transition(current, route)
    if target is None or target != "ESCALATING_TO_NURSE":
        raise ConflictError(f"Cannot escalate from state: {current}")

    repositories.update_rounding_session(
        session_id, status=target, updated_at=datetime.now()
    )

    escalation_id = str(uuid.uuid4())[:8]
    now = datetime.now()
    repositories.insert_nurse_escalation(
        {
            "id": escalation_id,
            "rounding_session_id": session_id,
            "request_id": None,
            "patient_id": session.get("patient_id"),
            "room": session.get("room"),
            "summary": summary,
            "priority": priority,
            "reason": reason,
            "suggested_action": suggested_action,
            "status": "PENDING",
            "created_at": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
            # Distinguishes this from workflow_service's
            # _raise_error_escalation() rows in /analytics/
            # escalation-breakdown and the nurse dashboard, now that
            # rounding_session_id alone (nullable) can't be used to tell
            # the two origins apart at a glance.
            "source": "rounding",
        }
    )
    _advance(session_id, "ESCALATING_TO_NURSE", "WAITING_FOR_NURSE_ACK")
    _log(
        RoundingEventType.ESCALATED,
        patient_id=session.get("patient_id"),
        previous_state=current,
        next_state="WAITING_FOR_NURSE_ACK",
        message=summary,
    )
    return {"escalation_id": escalation_id, "session": _view(session_id)}


def acknowledge_and_complete(session_id: str) -> dict:
    """WAITING_FOR_NURSE_ACK -> NURSE_ACKNOWLEDGED -> COMPLETED.

    Deliberately *not* called automatically by escalation_service's ack --
    a nurse acknowledging the escalation and the rounding session being
    marked complete are two different facts (see safety regression tests:
    WAITING_FOR_NURSE_ACK must never auto-advance to COMPLETED on its
    own). `escalation_service.acknowledge()` calls this explicitly after
    it acknowledges the escalation row, keeping the two tables' updates
    as one deliberate two-step operation rather than an implicit side
    effect."""
    session = _require_session(session_id)
    current = session["status"]
    _advance(session_id, current, "NURSE_ACKNOWLEDGED")
    _advance(session_id, "NURSE_ACKNOWLEDGED", "COMPLETED")
    repositories.update_rounding_session(session_id, ended_at=datetime.now())
    _log(
        RoundingEventType.ROUNDING_COMPLETED,
        patient_id=session.get("patient_id"),
        previous_state=current,
        next_state="COMPLETED",
        message="Nurse acknowledged",
    )
    return _view(session_id)


def require_delivery(
    session_id: str, request_type: str, patient_id: str | None = None
) -> dict:
    """The DELIVERY_REQUIRED branch out of NEED_CLASSIFIED: connects into
    the existing delivery workflow by creating a real `care_requests` /
    `robot_tasks` pair via `workflow_service.create_request()`, tagged
    `source="robot_rounding"` and linked back to this session. From that
    point on the new request follows `ALLOWED_TRANSITIONS`
    (robot_service.py) like any patient-tablet-originated request --
    including the untouched VERIFYING_PATIENT/KIT_RELEASED safety gates.

    Item 5 (multi-robot support): the delivery task is now assigned to
    *this session's own* `robot_id` (the robot actually doing the
    rounding), not silently defaulted to `workflow_service.
    DEFAULT_ROBOT_ID` as before -- a rounding robot other than the
    default one asking for a delivery no longer hands the task to a robot
    that was never at the bedside. `session["robot_id"]` is always set
    (start_rounding() requires it), so the `or` fallback below only
    matters for pre-item-5 rows in an existing database that predate the
    column being populated.

    The rounding session itself is left at DELIVERY_REQUIRED, not marked
    COMPLETED here -- it and the delivery task are two independently
    tracked things now (session id and request_id are what link them for
    reporting)."""
    session = _require_session(session_id)
    current = session["status"]
    target = rounding_branch_transition(current, "DELIVERY_REQUIRED")
    if target is None:
        raise ConflictError(f"Cannot require delivery from state: {current}")

    effective_patient_id = patient_id or session.get("patient_id")
    if not effective_patient_id:
        raise DomainError("patient_id is required to create a delivery request")

    repositories.update_rounding_session(
        session_id, status=target, updated_at=datetime.now()
    )
    result = workflow_service.create_request(
        request_type,
        patient_id=effective_patient_id,
        source="robot_rounding",
        rounding_session_id=session_id,
        robot_id=session.get("robot_id") or workflow_service.DEFAULT_ROBOT_ID,
    )
    _log(
        RoundingEventType.DELIVERY_REQUESTED,
        request_id=result["request_id"],
        patient_id=effective_patient_id,
        previous_state=current,
        next_state="DELIVERY_REQUIRED",
        message=f"Delivery request {result['request_id']} created from rounding",
    )
    return {"request_id": result["request_id"], "session": _view(session_id)}


def get_session(session_id: str) -> dict:
    return _require_session(session_id)


def list_active_sessions(robot_id: str | None = None) -> list:
    return repositories.list_active_rounding_sessions(robot_id=robot_id)
