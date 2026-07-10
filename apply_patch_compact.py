#!/usr/bin/env python3
"""Applies the escalation-timeout + delivery-error-escalation safety net
(roadmap items 1+2) as targeted find/replace edits, not full-file rewrites.

Run from the repo root (where backend/main.py lives):
    python3 apply_patch_compact.py

Each edit asserts its "old" snippet is found exactly once before replacing --
if a file has already been modified (or diverges from what this was built
against), it fails loudly with the file/index instead of silently
corrupting anything.
"""
import pathlib
import sys

ROOT = pathlib.Path(".")
if not (ROOT / "backend" / "main.py").exists():
    sys.exit("ERROR: run this from the repository root (directory containing backend/main.py).")

EDITS = [
    # -- backend/db/models.py --------------------------------------------
    ("backend/db/models.py",
     '''`robot_tasks` (see `backend/services/robot_service.py` for why).
"""''',
     '''`robot_tasks` (see `backend/services/robot_service.py` for why).

Escalation safety-net revision: `nurse_escalations.rounding_session_id`
switches from NOT NULL to nullable, and three columns are added
(`escalated_count`, `last_escalated_at`, `source`). This closes two gaps:
(1) a delivery-flow ERROR (QR mismatch, an attempted KIT_RELEASED without
nurse confirmation, an emergency stop) previously had no way to reach the
nurse_escalations queue at all, since every existing writer of that table
was rounding_service and always had a session to attach to --
`workflow_service._raise_error_escalation()` is the first writer that
doesn't; (2) a PENDING escalation could sit unacknowledged indefinitely
with no visible urgency change -- `escalation_service.
check_and_escalate_overdue()` now bumps priority one step after
`backend.core.config.ESCALATION_TIMEOUT_SECONDS` elapses, recording the
bump in these two new columns rather than silently mutating `priority`
with no trace.
"""'''),

    ("backend/db/models.py",
     '''class NurseEscalationRow(Base):
    """The queue of things a nurse needs to see and acknowledge.

    `request_id` is nullable: an escalation can exist purely as a
    notification (route == NURSE_NOTIFICATION, no delivery involved) with
    no corresponding `care_requests` row, or it can be raised alongside one
    (route == DELIVERY_REQUIRED plus a same-visit notification).
    """

    __tablename__ = "nurse_escalations"
    __table_args__ = (
        Index("ix_nurse_escalations_rounding_session_id", "rounding_session_id"),
        Index("ix_nurse_escalations_status", "status"),
    )

    id = Column(String, primary_key=True)
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=False
    )
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=True)
    patient_id = Column(String, nullable=True)
    room = Column(String, nullable=True)
    summary = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)''',
     '''class NurseEscalationRow(Base):
    """The queue of things a nurse needs to see and acknowledge.

    `request_id` is nullable: an escalation can exist purely as a
    notification (route == NURSE_NOTIFICATION, no delivery involved) with
    no corresponding `care_requests` row, or it can be raised alongside one
    (route == DELIVERY_REQUIRED plus a same-visit notification).

    `rounding_session_id` was originally NOT NULL (every escalation came
    from a rounding session). It is now nullable: `workflow_service`'s
    delivery flow raises an escalation directly on a safety-relevant
    ERROR (QR mismatch, an attempted KIT_RELEASED without nurse
    confirmation, emergency stop) without ever having a rounding session
    to attach to -- see `workflow_service._raise_error_escalation()`.
    `source` (nullable, "rounding" | "delivery_error") is how callers/UI
    tell the two origins apart without a schema change every time a third
    origin shows up.

    `escalated_count` / `last_escalated_at` back
    `escalation_service.check_and_escalate_overdue()`: a PENDING
    escalation left unacknowledged past its priority's timeout
    (`backend.core.config.ESCALATION_TIMEOUT_SECONDS`) has its priority
    bumped one step and these two fields updated, so the nurse dashboard
    can show "this was auto-escalated" instead of silently changing
    priority with no trace.
    """

    __tablename__ = "nurse_escalations"
    __table_args__ = (
        Index("ix_nurse_escalations_rounding_session_id", "rounding_session_id"),
        Index("ix_nurse_escalations_status", "status"),
    )

    id = Column(String, primary_key=True)
    rounding_session_id = Column(
        String, ForeignKey("rounding_sessions.id"), nullable=True
    )
    request_id = Column(String, ForeignKey("care_requests.id"), nullable=True)
    patient_id = Column(String, nullable=True)
    room = Column(String, nullable=True)
    summary = Column(Text, nullable=False)
    priority = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)
    escalated_count = Column(Integer, nullable=False, default=0)
    last_escalated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True)'''),

    # -- backend/core/config.py ------------------------------------------
    ("backend/core/config.py",
     'DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"',
     '''DEFAULT_PATIENT_ID = "PATIENT_A_ROOM_203"

# How long a PENDING nurse_escalations row may sit unacknowledged before
# escalation_service.check_and_escalate_overdue() bumps its priority one
# step (see ESCALATION_PRIORITY_ESCALATION_PATH below). Values are seconds;
# short enough to demo without a real wait, long enough that a nurse
# glancing at the dashboard every few refreshes isn't fighting the clock.
# Tune freely -- nothing else in the codebase assumes these exact numbers.
ESCALATION_TIMEOUT_SECONDS = {
    "URGENT": 120,
    "HIGH": 300,
    "MEDIUM": 600,
    "LOW": 1800,
}

# The one-step-up path a priority takes when it times out. URGENT maps to
# itself -- there is nowhere higher to go, so
# check_and_escalate_overdue() treats "next == current" as "already at the
# top" and leaves it alone rather than looping.
ESCALATION_PRIORITY_ESCALATION_PATH = {
    "LOW": "MEDIUM",
    "MEDIUM": "HIGH",
    "HIGH": "URGENT",
    "URGENT": "URGENT",
}'''),

    # -- backend/db/repositories.py ---------------------------------------
    ("backend/db/repositories.py",
     '''    "created_at",
    "acknowledged_at",
    "acknowledged_by",
]


def insert_rounding_session(row: dict) -> None:''',
     '''    "created_at",
    "acknowledged_at",
    "acknowledged_by",
    "escalated_count",
    "last_escalated_at",
    "source",
]


def insert_rounding_session(row: dict) -> None:'''),

    ("backend/db/repositories.py",
     '''def delete_all_data() -> None:''',
     '''def escalate_nurse_escalation_priority(
    escalation_id: str, new_priority: str, escalated_at: "datetime"
) -> None:
    """Bump one PENDING escalation's priority and record the bump.

    Used only by `escalation_service.check_and_escalate_overdue()` --
    never touches `status`/`acknowledged_*`, only `priority` plus the two
    trail columns, so a nurse can tell "this got louder while I wasn't
    looking" apart from "this was always URGENT"."""
    init_db()
    session = get_session()
    try:
        row = session.get(NurseEscalationRow, escalation_id)
        if row is not None:
            row.priority = new_priority
            row.escalated_count = (row.escalated_count or 0) + 1
            row.last_escalated_at = escalated_at
            session.commit()
    finally:
        session.close()


def delete_all_data() -> None:'''),

    # -- backend/services/escalation_service.py ---------------------------
    ("backend/services/escalation_service.py",
     '''from datetime import datetime

from backend.core.errors import ConflictError, NotFoundError
from backend.db import repositories
from backend.services import rounding_service


def get_escalation(escalation_id: str) -> dict:''',
     '''from datetime import datetime

from backend.core.config import (
    ESCALATION_PRIORITY_ESCALATION_PATH,
    ESCALATION_TIMEOUT_SECONDS,
)
from backend.core.errors import ConflictError, NotFoundError
from backend.db import repositories
from backend.services import rounding_service


def check_and_escalate_overdue(now: "datetime | None" = None) -> list:
    """Bump the priority of every PENDING escalation that has sat
    unacknowledged longer than its priority's timeout
    (`ESCALATION_TIMEOUT_SECONDS`).

    Called from `list_escalations_for_dashboard()` below -- i.e. on every
    `GET /escalations` -- rather than from a background scheduler. The
    nurse dashboard already polls that endpoint every few seconds
    (`ui/nurse_dashboard/app.py`'s auto-refresh), so a lazy check on read
    is enough to keep the queue's urgency current without adding a new
    always-running process to what is still a software-only prototype.

    Never touches ACKNOWLEDGED/CANCELLED rows, and never bumps a priority
    already at the top of `ESCALATION_PRIORITY_ESCALATION_PATH` (URGENT
    maps to itself) -- both are read as "nothing to do", not skipped
    silently in a way a caller needs to guard against. Does not send any
    notification through a real channel (no paging/SMS integration
    exists yet) -- the visible effect is the priority bump plus
    `escalated_count`/`last_escalated_at`, which the nurse dashboard
    already renders for every escalation it lists.

    Returns the list of escalations that were actually bumped (possibly
    empty), each in the same shape `get_escalation()` returns.
    """
    now = now or datetime.now()
    bumped = []
    for escalation in repositories.list_nurse_escalations(status="PENDING"):
        created_at = escalation["created_at"]
        if created_at is None:
            continue
        priority = escalation["priority"] or "LOW"
        timeout = ESCALATION_TIMEOUT_SECONDS.get(priority)
        if timeout is None:
            continue
        elapsed = (now - created_at).total_seconds()
        if elapsed < timeout:
            continue
        next_priority = ESCALATION_PRIORITY_ESCALATION_PATH.get(priority, priority)
        if next_priority == priority:
            continue
        repositories.escalate_nurse_escalation_priority(escalation["id"], next_priority, now)
        bumped.append(get_escalation(escalation["id"]))
    return bumped


def get_escalation(escalation_id: str) -> dict:'''),

    ("backend/services/escalation_service.py",
     '''def list_escalations_for_dashboard() -> list:
    """GET /escalations backing for the nurse dashboard's Escalations
    section (PR26): PENDING rows first (proposal doc: "PENDINGの通知を上に
    表示してください"), each group oldest-first so a nurse works the queue
    in the order things came in."""
    escalations = repositories.list_nurse_escalations()
    pending = [e for e in escalations if e["status"] == "PENDING"]
    other = [e for e in escalations if e["status"] != "PENDING"]
    return pending + other


def acknowledge(escalation_id: str, acknowledged_by: str) -> dict:
    """Nurse acknowledges one escalation. Also completes the rounding
    session it was raised from (via rounding_service.acknowledge_and_complete)
    -- one nurse action, two related facts recorded together, rather than
    the rounding session silently staying open forever after its one
    escalation is handled.

    Raises ConflictError (not a silent no-op) if the escalation is not
    PENDING -- mirrors workflow_service raising rather than swallowing an
    invalid-state transition. This is also the safety-relevant guarantee
    from the proposal doc's regression tests: acknowledging twice, or
    acknowledging something already RESOLVED/CANCELLED, is rejected
    rather than silently re-completing the session."""
    escalation = get_escalation(escalation_id)
    if escalation["status"] != "PENDING":
        raise ConflictError(
            f"Escalation {escalation_id} is not PENDING (status={escalation['status']})"
        )

    now = datetime.now()
    repositories.acknowledge_nurse_escalation(escalation_id, acknowledged_by, now)
    session = rounding_service.acknowledge_and_complete(escalation["rounding_session_id"])
    return {"escalation": get_escalation(escalation_id), "session": session}''',
     '''def list_escalations_for_dashboard() -> list:
    """GET /escalations backing for the nurse dashboard's Escalations
    section (PR26): PENDING rows first (proposal doc: "PENDINGの通知を上に
    表示してください"), each group oldest-first so a nurse works the queue
    in the order things came in.

    Runs check_and_escalate_overdue() first so any priority bump is
    reflected in the very same response a poll picks it up from -- a
    nurse should never see a stale (pre-bump) priority just because the
    bump and the read happened to race."""
    check_and_escalate_overdue()
    escalations = repositories.list_nurse_escalations()
    pending = [e for e in escalations if e["status"] == "PENDING"]
    other = [e for e in escalations if e["status"] != "PENDING"]
    return pending + other


def acknowledge(escalation_id: str, acknowledged_by: str) -> dict:
    """Nurse acknowledges one escalation. If it was raised from a rounding
    session, also completes that session (via
    rounding_service.acknowledge_and_complete) -- one nurse action, two
    related facts recorded together, rather than the rounding session
    silently staying open forever after its one escalation is handled.

    `rounding_session_id` is nullable: a delivery-flow escalation raised
    by `workflow_service._raise_error_escalation()` (QR mismatch,
    emergency stop, etc.) has no rounding session to complete, so
    `session` in the return value is None for those -- there is nothing
    else to advance once the escalation itself is acknowledged.

    Raises ConflictError (not a silent no-op) if the escalation is not
    PENDING -- mirrors workflow_service raising rather than swallowing an
    invalid-state transition. This is also the safety-relevant guarantee
    from the proposal doc's regression tests: acknowledging twice, or
    acknowledging something already RESOLVED/CANCELLED, is rejected
    rather than silently re-completing the session."""
    escalation = get_escalation(escalation_id)
    if escalation["status"] != "PENDING":
        raise ConflictError(
            f"Escalation {escalation_id} is not PENDING (status={escalation['status']})"
        )

    now = datetime.now()
    repositories.acknowledge_nurse_escalation(escalation_id, acknowledged_by, now)
    session = None
    if escalation.get("rounding_session_id"):
        session = rounding_service.acknowledge_and_complete(escalation["rounding_session_id"])
    return {"escalation": get_escalation(escalation_id), "session": session}'''),

    # -- backend/services/rounding_service.py -----------------------------
    ("backend/services/rounding_service.py",
     '''            "status": "PENDING",
            "created_at": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
        }
    )
    _advance(session_id, "ESCALATING_TO_NURSE", "WAITING_FOR_NURSE_ACK")''',
     '''            "status": "PENDING",
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
    _advance(session_id, "ESCALATING_TO_NURSE", "WAITING_FOR_NURSE_ACK")'''),

    # -- backend/services/workflow_service.py -----------------------------
    ("backend/services/workflow_service.py",
     "from backend.core.config import DEFAULT_PATIENT_ID, REQUEST_TYPES",
     "from backend.core.config import DEFAULT_PATIENT_ID, PATIENTS, REQUEST_TYPES"),

    ("backend/services/workflow_service.py",
     "def _view(request_id: str) -> dict | None:",
     '''def _raise_error_escalation(
    *, request_id: str, patient_id: str | None, summary: str, reason: str
) -> None:
    """Surface a delivery-flow ERROR in the same `nurse_escalations` queue
    the rounding workflow already raises into (rounding_service.escalate()
    / the nurse dashboard's Escalations section), instead of leaving it
    discoverable only via the task's ERROR state and the robot_events
    log.

    `rounding_session_id` is left None -- this escalation did not come
    from a rounding session, which is exactly why that column had to
    become nullable (see the migration and NurseEscalationRow's docstring
    in backend/db/models.py). `source="delivery_error"` is how
    /analytics/escalation-breakdown and the dashboard tell these apart
    from rounding-originated rows.

    Always raised at URGENT and never re-evaluated by
    escalation_service.check_and_escalate_overdue() past that point --
    every call site below is already a safety-relevant failure (a
    patient/kit mismatch, an attempt to release a kit without nurse
    confirmation, or a manual emergency stop), not something with a
    lower-urgency case to weigh the way need_classification_service does
    for the rounding flow. Failing to insert this row (e.g. a DB error)
    is deliberately not caught here -- it should surface the same way any
    other repositories.* failure would, rather than being swallowed
    silently right after a safety-relevant event.
    """
    room = PATIENTS.get(patient_id, {}).get("room") if patient_id else None
    now = datetime.now()
    repositories.insert_nurse_escalation(
        {
            "id": str(uuid.uuid4())[:8],
            "rounding_session_id": None,
            "request_id": request_id,
            "patient_id": patient_id,
            "room": room,
            "summary": summary,
            "priority": "URGENT",
            "reason": reason,
            "suggested_action": "至急、現場を確認し、ロボットの状態を確認してください。",
            "status": "PENDING",
            "created_at": now,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "source": "delivery_error",
        }
    )


def _view(request_id: str) -> dict | None:'''),

    ("backend/services/workflow_service.py",
     '''def advance_state(request_id: str, next_state: str) -> dict:
    task = _require_task(request_id)
    current = task["state"]
    now = datetime.now()

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
        raise DomainError(f"Invalid transition: {current} -> {next_state}")''',
     '''def advance_state(request_id: str, next_state: str) -> dict:
    task = _require_task(request_id)
    current = task["state"]
    now = datetime.now()
    req = repositories.get_care_request(request_id)
    patient_id = req.get("patient_id") if req else None

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
        _raise_error_escalation(
            request_id=request_id,
            patient_id=patient_id,
            summary=f"{patient_id or '不明な患者'} 宛のタスクで、看護師確認前にKIT_RELEASEDが試行されエラー停止しました。",
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
        _raise_error_escalation(
            request_id=request_id,
            patient_id=patient_id,
            summary=f"{patient_id or '不明な患者'} 宛のタスクで不正な状態遷移（{current} → {next_state}）が試行されエラー停止しました。",
            reason=f"Invalid transition {current} -> {next_state}",
        )
        raise DomainError(f"Invalid transition: {current} -> {next_state}")'''),

    ("backend/services/workflow_service.py",
     '''        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="patient_id mismatch",
        )
        raise DomainError("patient_id mismatch")''',
     '''        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="patient_id mismatch",
        )
        _raise_error_escalation(
            request_id=request_id,
            patient_id=req.get("patient_id"),
            summary=(
                f"{req.get('patient_id')} 宛のキットで患者ID不一致"
                f"（スキャン値: {patient_id}）によりエラー停止しました。"
            ),
            reason="patient_id mismatch",
        )
        raise DomainError("patient_id mismatch")'''),

    ("backend/services/workflow_service.py",
     '''        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="kit_id mismatch",
        )
        raise DomainError("kit_id mismatch")''',
     '''        _record_transition(
            task_id=task["id"],
            request_id=request_id,
            from_state="VERIFYING_PATIENT",
            to_state="ERROR",
            trigger_type="verification",
            triggered_by="verification_service",
            reason="kit_id mismatch",
        )
        _raise_error_escalation(
            request_id=request_id,
            patient_id=req.get("patient_id"),
            summary=(
                f"{req.get('patient_id')} 宛のキットでキットID不一致"
                f"（スキャン値: {kit_id}）によりエラー停止しました。"
            ),
            reason="kit_id mismatch",
        )
        raise DomainError("kit_id mismatch")'''),

    ("backend/services/workflow_service.py",
     '''    repositories.update_task_state(task["id"], "ERROR", now)
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
    raise DomainError(result["message"])''',
     '''    repositories.update_task_state(task["id"], "ERROR", now)
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
    _raise_error_escalation(
        request_id=request_id,
        patient_id=req.get("patient_id"),
        summary=f"{req.get('patient_id')} 宛のキットでQR照合NG（{result['message']}）によりエラー停止しました。",
        reason=result["message"],
    )
    raise DomainError(result["message"])'''),

    ("backend/services/workflow_service.py",
     '''def emergency_stop(request_id: str) -> dict:
    task = _require_task(request_id)
    now = datetime.now()
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
    return _view_or_error(request_id)''',
     '''def emergency_stop(request_id: str) -> dict:
    task = _require_task(request_id)
    now = datetime.now()
    prev = task["state"]
    req = repositories.get_care_request(request_id)
    patient_id = req.get("patient_id") if req else None
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
    _raise_error_escalation(
        request_id=request_id,
        patient_id=patient_id,
        summary=f"{patient_id or '不明な患者'} 宛のタスクで緊急停止が実行されました（直前の状態: {prev}）。",
        reason="Emergency stop triggered",
    )
    return _view_or_error(request_id)'''),

    # -- ui/nurse_dashboard/app.py -----------------------------------------
    ("ui/nurse_dashboard/app.py",
     '''            st.markdown(f"{esc.get('summary', '')}")
            if esc.get("suggested_action"):
                st.caption(f"Suggested action: {esc['suggested_action']}")
            if status == "PENDING":''',
     '''            st.markdown(f"{esc.get('summary', '')}")
            if esc.get("suggested_action"):
                st.caption(f"Suggested action: {esc['suggested_action']}")
            escalated_count = esc.get("escalated_count") or 0
            if escalated_count:
                st.caption(f"⚠️ 未確認のため優先度を自動引き上げ済み（{escalated_count}回）")
            if status == "PENDING":'''),

    # -- tests/test_rounding_repositories.py --------------------------------
    ("tests/test_rounding_repositories.py",
     '''    "status": "PENDING",
    "created_at": datetime(2026, 7, 9, 9, 2, 0),
    "acknowledged_at": None,
    "acknowledged_by": None,
}''',
     '''    "status": "PENDING",
    "created_at": datetime(2026, 7, 9, 9, 2, 0),
    "acknowledged_at": None,
    "acknowledged_by": None,
    # Added alongside the escalation-timeout safety net: escalated_count
    # defaults to 0 at the ORM level (NurseEscalationRow.escalated_count's
    # Column default) even though it isn't set explicitly here, but this
    # fixture spells it out (plus the two nullable additions) so this
    # test's exact-equality assertion keeps documenting the full row
    # shape rather than silently passing thanks to an ORM default.
    "escalated_count": 0,
    "last_escalated_at": None,
    "source": "rounding",
}'''),

    # -- tests/test_workflow_service.py (append new regression tests) -------
    ("tests/test_workflow_service.py",
     '''    assert repositories.get_active_task_for_robot("ROBOT_2") is not None
    # The first robot's task is unaffected by the second robot's task.
    assert repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID) is not None''',
     '''    assert repositories.get_active_task_for_robot("ROBOT_2") is not None
    # The first robot's task is unaffected by the second robot's task.
    assert repositories.get_active_task_for_robot(workflow_service.DEFAULT_ROBOT_ID) is not None


# ---------------------------------------------------------------------------
# Escalation safety net: every path that forces a task into ERROR should
# also raise a nurse_escalations row (see workflow_service.
# _raise_error_escalation()), so a nurse working the Escalations queue sees
# it without having to separately watch the delivery task list for ERROR.
# ---------------------------------------------------------------------------


def _pending_error_escalations() -> list:
    return [
        e
        for e in repositories.list_nurse_escalations(status="PENDING")
        if e["source"] == "delivery_error"
    ]


def test_verify_ids_patient_mismatch_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "PATIENT_B_ROOM_204", "KIT_TOILETING_A")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["request_id"] == request_id
    assert escalations[0]["priority"] == "URGENT"
    assert escalations[0]["rounding_session_id"] is None
    assert "patient_id mismatch" in escalations[0]["reason"]


def test_verify_ids_kit_mismatch_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE", "VERIFYING_PATIENT"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(DomainError):
        workflow_service.verify_ids(request_id, "PATIENT_A_ROOM_203", "KIT_WATER")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert "kit_id mismatch" in escalations[0]["reason"]


def test_kit_released_without_confirmation_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    for s in ["KIT_SELECTED", "MOVING_TO_BEDSIDE"]:
        workflow_service.advance_state(request_id, s)

    with pytest.raises(ForbiddenError):
        workflow_service.advance_state(request_id, "KIT_RELEASED")

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["request_id"] == request_id
    assert escalations[0]["priority"] == "URGENT"


def test_emergency_stop_raises_nurse_escalation(robot_storage):
    result = workflow_service.create_request("toileting")
    request_id = result["request_id"]
    workflow_service.advance_state(request_id, "KIT_SELECTED")

    workflow_service.emergency_stop(request_id)

    escalations = _pending_error_escalations()
    assert len(escalations) == 1
    assert escalations[0]["patient_id"] == "PATIENT_A_ROOM_203"
    assert escalations[0]["priority"] == "URGENT"
    assert "Emergency stop" in escalations[0]["reason"]'''),

    # -- tests/test_escalation_service.py (imports + append new tests) ------
    ("tests/test_escalation_service.py",
     '''"""Tests for backend.services.escalation_service."""
import pytest

from backend.core.errors import ConflictError, NotFoundError
from backend.services import escalation_service, rounding_service''',
     '''"""Tests for backend.services.escalation_service."""
from datetime import datetime, timedelta

import pytest

from backend.core.errors import ConflictError, NotFoundError
from backend.db import repositories
from backend.services import escalation_service, rounding_service'''),

    ("tests/test_escalation_service.py",
     '''def test_list_escalations_for_dashboard_sorts_pending_first(robot_storage):
    _session1, esc1 = _escalated_session()
    _session2, esc2 = _escalated_session()
    # Acknowledge the first-created one, leaving the second PENDING.
    escalation_service.acknowledge(esc1, "nurse_demo")

    ordered = escalation_service.list_escalations_for_dashboard()
    assert ordered[0]["id"] == esc2
    assert ordered[0]["status"] == "PENDING"
    assert ordered[1]["id"] == esc1
    assert ordered[1]["status"] == "ACKNOWLEDGED"''',
     '''def test_list_escalations_for_dashboard_sorts_pending_first(robot_storage):
    _session1, esc1 = _escalated_session()
    _session2, esc2 = _escalated_session()
    # Acknowledge the first-created one, leaving the second PENDING.
    escalation_service.acknowledge(esc1, "nurse_demo")

    ordered = escalation_service.list_escalations_for_dashboard()
    assert ordered[0]["id"] == esc2
    assert ordered[0]["status"] == "PENDING"
    assert ordered[1]["id"] == esc1
    assert ordered[1]["status"] == "ACKNOWLEDGED"


# ---------------------------------------------------------------------------
# check_and_escalate_overdue() / the escalation-timeout safety net.
# ---------------------------------------------------------------------------


def _insert_escalation(
    escalation_id: str, priority: str, created_at: "datetime", status: str = "PENDING"
) -> None:
    repositories.insert_nurse_escalation(
        {
            "id": escalation_id,
            "rounding_session_id": None,
            "request_id": None,
            "patient_id": "PATIENT_A_ROOM_203",
            "room": "203",
            "summary": "test escalation",
            "priority": priority,
            "reason": None,
            "suggested_action": None,
            "status": status,
            "created_at": created_at,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "source": "rounding",
        }
    )


def test_check_and_escalate_overdue_bumps_priority_past_timeout(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-overdue", "HIGH", created_at)
    now = created_at + timedelta(seconds=301)  # HIGH's timeout is 300s

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert [e["id"] for e in bumped] == ["esc-overdue"]
    escalation = escalation_service.get_escalation("esc-overdue")
    assert escalation["priority"] == "URGENT"
    assert escalation["escalated_count"] == 1
    assert escalation["last_escalated_at"] == now


def test_check_and_escalate_overdue_leaves_recent_escalations_alone(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-recent", "HIGH", created_at)
    now = created_at + timedelta(seconds=100)  # well under HIGH's 300s timeout

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    escalation = escalation_service.get_escalation("esc-recent")
    assert escalation["priority"] == "HIGH"
    assert escalation["escalated_count"] == 0


def test_check_and_escalate_overdue_ignores_acknowledged_escalations(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-acked", "HIGH", created_at, status="ACKNOWLEDGED")
    now = created_at + timedelta(hours=1)

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    assert escalation_service.get_escalation("esc-acked")["priority"] == "HIGH"


def test_check_and_escalate_overdue_urgent_stays_urgent(robot_storage):
    created_at = datetime(2026, 7, 10, 9, 0, 0)
    _insert_escalation("esc-urgent", "URGENT", created_at)
    now = created_at + timedelta(hours=1)

    bumped = escalation_service.check_and_escalate_overdue(now=now)

    assert bumped == []
    escalation = escalation_service.get_escalation("esc-urgent")
    assert escalation["priority"] == "URGENT"
    assert escalation["escalated_count"] == 0


def test_list_escalations_for_dashboard_triggers_overdue_bump(robot_storage):
    old_created_at = datetime.now() - timedelta(hours=1)
    _insert_escalation("esc-stale", "MEDIUM", old_created_at)

    ordered = escalation_service.list_escalations_for_dashboard()

    stale = next(e for e in ordered if e["id"] == "esc-stale")
    assert stale["priority"] == "HIGH"
    assert stale["escalated_count"] == 1


# ---------------------------------------------------------------------------
# acknowledge() against an escalation with no rounding session (raised by
# workflow_service._raise_error_escalation() instead of rounding_service).
# ---------------------------------------------------------------------------


def test_acknowledge_without_rounding_session_returns_none_session(robot_storage):
    repositories.insert_nurse_escalation(
        {
            "id": "esc-delivery-error",
            "rounding_session_id": None,
            "request_id": "req-123",
            "patient_id": "PATIENT_A_ROOM_203",
            "room": "203",
            "summary": "QR mismatch",
            "priority": "URGENT",
            "reason": "patient_id mismatch",
            "suggested_action": None,
            "status": "PENDING",
            "created_at": datetime.now(),
            "acknowledged_at": None,
            "acknowledged_by": None,
            "source": "delivery_error",
        }
    )

    result = escalation_service.acknowledge("esc-delivery-error", "nurse_demo")

    assert result["session"] is None
    assert result["escalation"]["status"] == "ACKNOWLEDGED"'''),
]

NEW_FILES = {
    "alembic/versions/9c1f2b6a7d3e_nurse_escalation_safety_net.py": '''"""nurse_escalations: nullable rounding_session_id + auto-escalation fields

Revision ID: 9c1f2b6a7d3e
Revises: 71a902b00d13
Create Date: 2026-07-10 12:00:00.000000

Hand-written (not autogenerate), same reason as PR15/PR22: SQLite cannot
ALTER a column's nullability or add a column with a server default outside
of batch mode, so this whole migration runs inside a single
`op.batch_alter_table(...)` block.

Two independent changes bundled into one revision because they land in the
same table and the same feature (see `backend/db/models.py`'s
`NurseEscalationRow` docstring for the full rationale):

  - `rounding_session_id` NOT NULL -> nullable, so a delivery-flow ERROR
    (raised by `workflow_service._raise_error_escalation()`, which has no
    rounding session to attach to) can be inserted at all.
  - `escalated_count` (Integer, NOT NULL, default 0), `last_escalated_at`
    (DateTime, nullable), `source` (String, nullable) support
    `escalation_service.check_and_escalate_overdue()`'s priority-bump
    trail and let callers tell a rounding-originated escalation apart
    from a delivery-error one.

`escalated_count` needs `server_default='0'` (not just the ORM-side
`default=0` in models.py) because existing rows in a real deployment's
table already exist at migration time and must satisfy the new NOT NULL
constraint immediately -- the ORM-side default only applies to rows
inserted after the model change is loaded, not to rows already on disk.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c1f2b6a7d3e'
down_revision: Union[str, Sequence[str], None] = '71a902b00d13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('nurse_escalations', schema=None) as batch_op:
        batch_op.alter_column(
            'rounding_session_id',
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                'escalated_count',
                sa.Integer(),
                nullable=False,
                server_default='0',
            )
        )
        batch_op.add_column(sa.Column('last_escalated_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('source', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema.

    NOTE: if any row was inserted with `rounding_session_id IS NULL` (i.e.
    any delivery-flow error escalation exists), re-adding the NOT NULL
    constraint below will fail -- that data loss/conflict has to be
    resolved by hand (delete or backfill those rows) before downgrading
    past this revision. This is a deliberate one-way door, not an
    oversight: the whole point of this revision is that such rows are now
    valid.
    """
    with op.batch_alter_table('nurse_escalations', schema=None) as batch_op:
        batch_op.drop_column('source')
        batch_op.drop_column('last_escalated_at')
        batch_op.drop_column('escalated_count')
        batch_op.alter_column(
            'rounding_session_id',
            existing_type=sa.String(),
            nullable=False,
        )
''',
}

for relpath, old, new in EDITS:
    path = ROOT / relpath
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        sys.exit(f"ERROR: expected exactly 1 match for a snippet in {relpath}, found {count}. Aborting before any further changes.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"patched {relpath}")

for relpath, content in NEW_FILES.items():
    path = ROOT / relpath
    if path.exists():
        print(f"skipped {relpath} (already exists)")
        continue
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"created {relpath}")

print("All targeted edits applied.")
