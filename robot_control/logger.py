import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "robot_log.json"

def append_log(event_type, patient_id="â", request="â", kit="â",
               previous_state="â", next_state="â", result="â", message=""):
    logs = []
    if LOG_FILE.exists():
        with open(LOG_FILE, encoding="utf-8") as f:
            logs = json.load(f)
    logs.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "patient_id": patient_id,
        "request": request,
        "kit": kit,
        "previous_state": previous_state,
        "next_state": next_state,
        "result": result,
        "message": message,
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

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
