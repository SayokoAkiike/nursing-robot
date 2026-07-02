import sys
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from backend.storage import append_log_entry

def append_log(
    event_type: str,
    patient_id: str = "—",
    request: str = "—",
    kit: str = "—",
    previous_state: str = "—",
    next_state: str = "—",
    result: str = "—",
    message: str = "",
):
    append_log_entry({
        "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type":     event_type,
        "patient_id":     patient_id,
        "request":        request,
        "kit":            kit,
        "previous_state": previous_state,
        "next_state":     next_state,
        "result":         result,
        "message":        message,
    })

class EventType:
    REQUEST_CREATED  = "REQUEST_CREATED"
    STATE_TRANSITION = "STATE_TRANSITION"
    QR_OK            = "QR_OK"
    QR_NG            = "QR_NG"
    CANCEL           = "CANCEL"
    EMERGENCY_STOP   = "EMERGENCY_STOP"
    ERROR            = "ERROR"
    RESET            = "RESET"
    COMPLETED        = "COMPLETED"
