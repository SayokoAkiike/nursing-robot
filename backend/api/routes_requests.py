"""Care-request endpoints.
 
Note: until PR3 ("Task resource model") lands, the backing store only ever
holds a single in-flight request (see `backend/db/repositories.py`). The
`request_id` path parameter is used for existence checks (404 vs 200) but
does not yet select among multiple concurrent tasks -- there is only ever
one. `list_requests()` reflects this: it returns at most one item.
"""
from fastapi import APIRouter
 
from backend.schemas.request import RequestCreate
from backend.services import workflow_service
 
router = APIRouter(tags=["requests"])
 
 
@router.get("/state")
def get_state():
    return workflow_service.get_current_state()
 
 
@router.get("/requests")
def list_requests():
    return workflow_service.list_requests()
 
 
@router.post("/requests")
def create_request(body: RequestCreate):
    return workflow_service.create_request(body.request_type, patient_id=body.patient_id)
 
 
@router.get("/requests/{request_id}")
def get_request(request_id: str):
    return workflow_service.require_request(request_id)
 
 
@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: str):
    workflow_service.require_request(request_id)
    return workflow_service.cancel_request()
 
