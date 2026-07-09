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

from backend.core.errors import ConflictError, NotFoundError
from backend.db import repositories
from backend.services import rounding_service


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
    return {"escalation": get_escalation(escalation_id), "session": session}
