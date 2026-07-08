"""Care-request endpoints.

Since PR3 ("Task resource model"), `request_id` genuinely identifies one
`care_requests` row joined to its `robot_tasks` row -- it is no longer just
a 404 guard in front of a single shared slot. Multiple requests can exist;
at most one per robot may be *active* at a time (see
`backend/services/workflow_service.py`'s concurrency rule).
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
    return workflow_service.cancel_request(request_id, actor="patient")

