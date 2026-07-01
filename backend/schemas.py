from pydantic import BaseModel
from typing import Optional

class RequestCreate(BaseModel):
    request_type: str  # toileting / water / nurse_check

class TransitionRequest(BaseModel):
    next_state: str

class VerifyRequest(BaseModel):
    patient_id: str
    kit_id: str
