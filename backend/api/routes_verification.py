from fastapi import APIRouter, Depends

from backend.core.security import require_nurse
from backend.schemas.verification import VerifyRequest
from backend.services import workflow_service

router = APIRouter(prefix="/tasks/{request_id}", tags=["verification"], dependencies=[Depends(require_nurse)])


@router.post("/verify")
def verify(request_id: str, body: VerifyRequest):
    return workflow_service.verify_ids(request_id, body.patient_id, body.kit_id)

