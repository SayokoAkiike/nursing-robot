from pydantic import BaseModel
 
from backend.core.config import DEFAULT_PATIENT_ID
 
 
class RequestCreate(BaseModel):
    request_type: str
    patient_id: str = DEFAULT_PATIENT_ID
 
