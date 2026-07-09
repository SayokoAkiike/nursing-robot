"""Nurse escalation queue endpoints.

`ack` is nurse-authenticated (mirrors `routes_tasks.py` /
`routes_verification.py`'s use of `require_nurse`); `GET /escalations` is
not, matching `GET /requests`'s precedent of being a read-only view
anyone with API access can see.
"""
from fastapi import APIRouter, Depends

from backend.core.security import require_nurse
from backend.schemas.rounding import AckRequest
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


@router.post("/{escalation_id}/ack", dependencies=[Depends(require_nurse)])
def acknowledge(escalation_id: str, body: AckRequest):
    result = escalation_service.acknowledge(escalation_id, body.acknowledged_by)
    return {"escalation": result["escalation"], "rounding_session": result["session"]}
