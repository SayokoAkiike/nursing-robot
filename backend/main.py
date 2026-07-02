import sys, os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import RequestCreate, TransitionRequest, VerifyRequest
from backend.auth import require_nurse
from backend import storage
from robot_control import service

app = FastAPI(title="PreCare Dock API", version="0.3.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:8502").split(",")
app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type", "x-nurse-token"])

@app.get("/state")
def get_state(): return service.get_current_state()

@app.post("/requests")
def create_request(body: RequestCreate):
    try: return service.create_request(body.request_type, patient_id=body.patient_id)
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/transition")
def transition(body: TransitionRequest, _=Depends(require_nurse)):
    try: return service.advance_state(body.next_state)
    except ValueError as e: raise HTTPException(403 if "nurse" in str(e).lower() else 400, str(e))

@app.post("/verify")
def verify_ids(body: VerifyRequest, _=Depends(require_nurse)):
    try: return service.verify_ids(body.patient_id, body.kit_id)
    except ValueError as e: raise HTTPException(409 if "VERIFYING" in str(e) else 400, str(e))

@app.post("/emergency-stop")
def emergency_stop(_=Depends(require_nurse)): return service.emergency_stop()

@app.post("/reset")
def reset(_=Depends(require_nurse)): return service.reset()

@app.post("/cancel")
def cancel(_=Depends(require_nurse)):
    try: return service.cancel_request()
    except ValueError as e: raise HTTPException(400, str(e))

@app.get("/logs")
def get_logs(): return storage.load_logs()

@app.get("/requests")
def list_requests(): return storage.load_requests()

@app.get("/requests/{request_id}")
def get_request(request_id: str):
    req = storage.get_request(request_id)
    if not req: raise HTTPException(404, "Request not found")
    return req

@app.post("/requests/{request_id}/cancel")
def cancel_by_id(request_id: str):
    if not storage.get_request(request_id): raise HTTPException(404, "Request not found")
    try: return service.cancel_request()
    except ValueError as e: raise HTTPException(400, str(e))

@app.post("/tasks/{request_id}/transition")
def transition_by_id(request_id: str, body: TransitionRequest, _=Depends(require_nurse)):
    if not storage.get_request(request_id): raise HTTPException(404, "Request not found")
    try: return service.advance_state(body.next_state)
    except ValueError as e: raise HTTPException(403 if "nurse" in str(e).lower() else 400, str(e))

@app.post("/tasks/{request_id}/verify")
def verify_by_id(request_id: str, body: VerifyRequest, _=Depends(require_nurse)):
    if not storage.get_request(request_id): raise HTTPException(404, "Request not found")
    try: return service.verify_ids(body.patient_id, body.kit_id)
    except ValueError as e: raise HTTPException(409 if "VERIFYING" in str(e) else 400, str(e))

@app.post("/tasks/{request_id}/emergency-stop")
def emergency_stop_by_id(request_id: str, _=Depends(require_nurse)):
    if not storage.get_request(request_id): raise HTTPException(404, "Request not found")
    return service.emergency_stop()

@app.post("/tasks/{request_id}/reset")
def reset_by_id(request_id: str, _=Depends(require_nurse)):
    if not storage.get_request(request_id): raise HTTPException(404, "Request not found")
    return service.reset()
