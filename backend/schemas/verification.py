from pydantic import BaseModel
 
 
class VerifyRequest(BaseModel):
    patient_id: str
    kit_id: str
 
