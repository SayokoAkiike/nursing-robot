from pydantic import BaseModel
from robot_control.config import DEFAULT_PATIENT_ID

class RequestCreate(BaseModel):
    request_type: str
    patient_id: str = DEFAULT_PATIENT_ID

class TransitionRequest(BaseModel):
    next_state: str

class VerifyRequest(BaseModel):
    patient_id: str
    kit_id: str
