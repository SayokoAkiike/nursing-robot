"""Robot-task state-transition endpoints (nurse-authenticated).

Since PR3, `request_id` selects a real `robot_tasks` row (via its
`request_id` column) -- see the note in `routes_requests.py`.
"""
from fastapi import APIRouter, Depends

from backend.core.security import require_nurse
from backend.schemas.task import TransitionRequest
from backend.services import workflow_service

router = APIRouter(prefix="/tasks/{request_id}", tags=["tasks"], dependencies=[Depends(require_nurse)])


@router.post("/transition")
def transition(request_id: str, body: TransitionRequest):
    return workflow_service.advance_state(request_id, body.next_state)


@router.post("/emergency-stop")
def emergency_stop(request_id: str):
    return workflow_service.emergency_stop(request_id)


@router.post("/reset")
def reset(request_id: str):
    return workflow_service.reset(request_id)


@router.post("/cancel")
def cancel(request_id: str):
    """Nurse-side cancel (authenticated; only legal from early states)."""
    return workflow_service.cancel_request(request_id)

