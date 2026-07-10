from pydantic import BaseModel

from backend.core.config import DEFAULT_PATIENT_ID
from backend.services.workflow_service import DEFAULT_ROBOT_ID


class RequestCreate(BaseModel):
    request_type: str
    patient_id: str = DEFAULT_PATIENT_ID
    # Item 5 (multi-robot support): defaults to the same robot every caller
    # already implicitly used, mirroring RoundingStart.robot_id in
    # backend/schemas/rounding.py. Existing callers that don't send this
    # field keep getting assigned to DEFAULT_ROBOT_ID, unchanged.
    robot_id: str = DEFAULT_ROBOT_ID

