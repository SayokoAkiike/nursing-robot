"""Nurse escalation queue endpoints.

`ack` is nurse-authenticated (mirrors `routes_tasks.py` /
`routes_verification.py`'s use of `require_nurse`); `GET /escalations` is
not, matching `GET /requests`'s precedent of being a read-only view
anyone with API access can see. `vision-report` is robot-authenticated
(`require_robot`, PR35 follow-up) -- see `backend/core/config.py`'s
`Settings.robot_token` docstring for why this one specifically needed a
token while /rounding/*'s unauthenticated endpoints didn't.
"""
from fastapi import APIRouter, Depends

from backend.core.security import require_nurse, require_robot
from backend.schemas.rounding import AckRequest, VisionEscalationRequest
from backend.services import escalation_service

router = APIRouter(prefix="/escalations", tags=["escalations"])


@router.get("")
def list_escalations(status: str | None = None):
    """PENDING-first ordering for the nurse dashboard (PR26), unless a
    specific `status` filter is requested, in which case that's a plain
    filtered list (sorting PENDING-first would be meaningless against a
    single-status result)."""
    if status is not None:
        return escalation_service.list_escalations(status=status)
    return escalation_service.list_escalations_for_dashboard()


@router.get("/{escalation_id}")
def get_escalation(escalation_id: str):
    return escalation_service.get_escalation(escalation_id)


@router.post("/vision-report", dependencies=[Depends(require_robot)])
def report_vision_escalation(body: VisionEscalationRequest):
    """PR30: represents a sensor/robot observation (a camera seeing a
    patient leave the bed unsupervised), not a nurse action -- but
    unlike /rounding/*'s endpoints, this one is a stateless, one-shot
    write with no prior session/state-machine gate, so it needed its
    own auth (require_robot, PR35 follow-up) rather than staying
    unauthenticated. See routes_rounding.py's own docstring for the
    contrasting "unauthenticated is fine because state-gated" reasoning
    that endpoint family still relies on."""
    return escalation_service.raise_direct_escalation(
        room=body.room,
        patient_id=body.patient_id,
        summary=body.summary,
        priority=body.priority,
        reason=body.reason,
        suggested_action=body.suggested_action,
        source="vision_pose",
    )


@router.post("/{escalation_id}/ack", dependencies=[Depends(require_nurse)])
def acknowledge(escalation_id: str, body: AckRequest):
    result = escalation_service.acknowledge(escalation_id, body.acknowledged_by)
    return {"escalation": result["escalation"], "rounding_session": result["session"]}
