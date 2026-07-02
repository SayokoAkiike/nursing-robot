import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import RequestCreate, TransitionRequest, VerifyRequest
from backend.auth import require_nurse
from fastapi import Depends
from backend.auth import require_nurse
from fastapi import Depends
from backend.storage import load_logs
from robot_control import service

app = FastAPI(title="PreCare Dock API", version="0.2.0")

# WARNING: 開発・研究用。本番・実機利用時は allow_origins を制限すること
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"])

@app.get("/state")
def get_state():
    return service.get_current_state()

@app.post("/requests")
def create_request(body: RequestCreate):
    try:
        return service.create_request(body.request_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/transition")
def transition(body: TransitionRequest, _=Depends(require_nurse)):
    try:
        return service.advance_state(body.next_state)
    except ValueError as e:
        code = 403 if "nurse confirmation" in str(e).lower() else 400
        raise HTTPException(status_code=code, detail=str(e))

@app.post("/verify")
def verify_ids(body: VerifyRequest, _=Depends(require_nurse)):
    try:
        return service.verify_ids(body.patient_id, body.kit_id)
    except ValueError as e:
        code = 409 if "VERIFYING_PATIENT" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))

@app.post("/emergency-stop")
def emergency_stop(_=Depends(require_nurse)):
    return service.emergency_stop()

@app.post("/reset")
def reset(_=Depends(require_nurse)):
    return service.reset()

@app.post("/cancel")
def cancel(_=Depends(require_nurse)):
    return service.cancel_request()

@app.get("/logs")
def get_logs():
    return load_logs()
