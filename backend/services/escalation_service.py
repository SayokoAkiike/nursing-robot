"""Nurse-facing operations on the `nurse_escalations` queue (PR23).

Split out from `rounding_service.py` because the two have different
callers/actors: `rounding_service` functions are called as the *robot*
progresses a session; this module's `acknowledge()` is called by a *nurse*
action (mirrors why `workflow_service.py` keeps nurse-authenticated
transitions -- advance_state/emergency_stop/reset/cancel(actor="nurse") --
conceptually distinct from the patient-triggered create_request/cancel,
even though PR23 doesn't split those into separate modules the way this
one is split out for rounding).
"""
from datetime import datetime

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


def get_escalation(escalation_id: str) -> dict:
    escalation = repositories.get_nurse_escalation(escalation_id)
    if escalation is None:
        raise NotFoundError("Escalation not found")
    return escalation


def list_escalations(status: str | None = None) -> list:
    return repositories.list_nurse_escalations(status=status)


def list_escalations_for_dashboard() -> list:
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
    return {"escalation": get_escalation(escalation_id), "session": session}
