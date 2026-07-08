"""Robot-task state-transition endpoints (nurse-authenticated).
 
See the note in `routes_requests.py` about the current single-task
limitation: `request_id` gates 404s but all tasks currently share one
underlying robot state.
"""
from fastapi import APIRouter, Depends
 
from backend.core.security import require_nurse
from backend.schemas.task import TransitionRequest
from backend.services import workflow_service
 
router = APIRouter(prefix="/tasks/{request_id}", tags=["tasks"], dependencies=[Depends(require_nurse)])
 
 
@router.post("/transition")
def transition(request_id: str, body: TransitionRequest):
    workflow_service.require_request(request_id)
    return workflow_service.advance_state(body.next_state)
 
 
@router.post("/emergency-stop")
def emergency_stop(request_id: str):
    workflow_service.require_request(request_id)
    return workflow_service.emergency_stop()
 
 
@router.post("/reset")
def reset(request_id: str):
    workflow_service.require_request(request_id)
    return workflow_service.reset()
 
 
@router.post("/cancel")
def cancel(request_id: str):
    """Nurse-side cancel (authenticated; only legal from early states)."""
    workflow_service.require_request(request_id)
    return workflow_service.cancel_request()
 
