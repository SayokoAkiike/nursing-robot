import sys
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.storage import load_state, save_state, load_logs, append_log_entry
from backend.schemas import RequestCreate, TransitionRequest, VerifyRequest
from robot_control.state_machine import RobotState, NORMAL_FLOW, ALLOWED_TRANSITIONS
from vision.qr_detection.verify_patient_kit import verify

app = FastAPI(title="PreCare Dock API", version="0.1.0")

# WARNING: 開発・研究用。本番・実機利用時は allow_origins を制限すること
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"])

REQUEST_MAP = {
    "toileting":   {"request": "Toileting preparation", "kit": "KIT_TOILETING_A", "risk": "転倒リスクあり", "patient_id": "PATIENT_A_ROOM_203"},
    "water":       {"request": "Water request",         "kit": "KIT_WATER",        "risk": "なし",           "patient_id": "PATIENT_A_ROOM_203"},
    "nurse_check": {"request": "Nurse check",           "kit": "ALERT_NURSE_ONLY", "risk": "要確認",         "patient_id": "PATIENT_A_ROOM_203"},
}

# 遷移ルールは robot_control/state_machine.py の ALLOWED_TRANSITIONS を使用

def log(event_type, state, prev=None, msg=""):
    append_log_entry({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event_type": event_type,
        "patient_id": state.get("patient_id", "—"),
        "request": state.get("request", "—"),
        "kit": state.get("kit", "—"),
        "previous_state": prev or "—",
        "next_state": state.get("robot_state", "—"),
        "result": "OK" if "ERROR" not in state.get("robot_state", "") else "NG",
        "message": msg,
    })

@app.get("/state")
def get_state():
    return load_state()

@app.post("/requests")
def create_request(body: RequestCreate):
    state = load_state()
    if state.get("robot_state") not in ["IDLE", "COMPLETED", "ERROR"]:
        raise HTTPException(status_code=409, detail="Another request is in progress")
    info = REQUEST_MAP.get(body.request_type)
    if not info:
        raise HTTPException(status_code=400, detail=f"Unknown request_type: {body.request_type}")
    new_state = {**info, "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()}
    save_state(new_state)
    log("REQUEST_CREATED", new_state, prev="IDLE", msg=f"{body.request_type} request created")
    return new_state

@app.post("/transition")
def transition(body: TransitionRequest):
    state = load_state()
    current = state.get("robot_state", "IDLE")
    allowed = ALLOWED_TRANSITIONS.get(current)
    if body.next_state == "KIT_RELEASED" and current != "WAITING_FOR_NURSE_CONFIRMATION":
        state["robot_state"] = "ERROR"
        save_state(state)
        log("ERROR", state, prev=current, msg="KIT_RELEASED attempted without nurse confirmation")
        raise HTTPException(status_code=403, detail="Nurse confirmation required before KIT_RELEASED")
    if allowed != body.next_state:
        state["robot_state"] = "ERROR"
        save_state(state)
        log("ERROR", state, prev=current, msg=f"Invalid transition {current} -> {body.next_state}")
        raise HTTPException(status_code=400, detail=f"Invalid transition: {current} -> {body.next_state}")
    prev = current
    state["robot_state"] = body.next_state
    save_state(state)
    log("STATE_TRANSITION", state, prev=prev)
    return state

@app.post("/verify")
def verify_ids(body: VerifyRequest):
    state = load_state()
    if state.get("robot_state") != "VERIFYING_PATIENT":
        raise HTTPException(status_code=409, detail="Not in VERIFYING_PATIENT state")
    if body.patient_id != state.get("patient_id"):
        raise HTTPException(status_code=400, detail="patient_id mismatch")
    if body.kit_id != state.get("kit"):
        raise HTTPException(status_code=400, detail="kit_id mismatch")
    result = verify(body.patient_id, body.kit_id)
    if result["ok"]:
        state["robot_state"] = "DOCKING"
        save_state(state)
        log("QR_OK", state, prev="VERIFYING_PATIENT", msg=result["message"])
        return {"ok": True, "state": state}
    else:
        state["robot_state"] = "ERROR"
        save_state(state)
        log("QR_NG", state, prev="VERIFYING_PATIENT", msg=result["message"])
        raise HTTPException(status_code=400, detail=result["message"])

@app.post("/emergency-stop")
def emergency_stop():
    state = load_state()
    prev = state.get("robot_state", "IDLE")
    state["robot_state"] = "ERROR"
    save_state(state)
    log("EMERGENCY_STOP", state, prev=prev, msg="Emergency stop triggered")
    return state

@app.post("/reset")
def reset():
    state = load_state()
    prev = state.get("robot_state", "ERROR")
    new_state = {"request": None, "robot_state": "IDLE"}
    save_state(new_state)
    log("RESET", new_state, prev=prev, msg="Reset to IDLE")
    return new_state

@app.get("/logs")
def get_logs():
    return load_logs()
