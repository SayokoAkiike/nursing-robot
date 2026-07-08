from pydantic import BaseModel
 
 
class LogEntry(BaseModel):
    timestamp: str
    event_type: str
    patient_id: str = "—"
    request: str = "—"
    kit: str = "—"
    previous_state: str = "—"
    next_state: str = "—"
    result: str = "—"
    message: str = ""
 
