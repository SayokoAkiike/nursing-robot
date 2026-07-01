import streamlit as st
import json, time, sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "shared_state.json"
LOG_FILE   = DATA_DIR / "robot_log.json"

sys.path.insert(0, str(ROOT_DIR))
from robot_control.state_machine import STATE_MESSAGES
from robot_control.logger import append_log, EventType
from vision.qr_detection.verify_patient_kit import verify
from ui.common.style import CSS, LABELS

st.set_page_config(page_title=LABELS["app_nurse"], layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def log_event(event_type, s, prev=None, msg=""):
    append_log(event_type=event_type,
        patient_id=s.get("patient_id","—"), request=s.get("request","—"),
        kit=s.get("kit","—"), previous_state=prev or "—",
        next_state=s.get("robot_state","—"),
        result="OK" if "ERROR" not in s.get("robot_state","") else "NG",
        message=msg)

NEXT = {
    "REQUEST_RECEIVED": "KIT_SELECTED",
    "KIT_SELECTED": "MOVING_TO_BEDSIDE",
    "MOVING_TO_BEDSIDE": "VERIFYING_PATIENT",
    "VERIFYING_PATIENT": "DOCKING",
    "DOCKING": "TRAY_LIFTING",
    "TRAY_LIFTING": "WAITING_FOR_NURSE_CONFIRMATION",
    "WAITING_FOR_NURSE_CONFIRMATION": "KIT_RELEASED",
    "KIT_RELEASED": "COMPLETED",
}
FLOW = list(NEXT.keys()) + ["COMPLETED"]
RISK_COLOR = {"転倒リスクあり": "High", "要確認": "Check", "なし": "Low"}

col_h1, col_h2 = st.columns([3,1])
with col_h1:
    st.markdown(f"## {LABELS[chr(39)+'app_nurse'+chr(39)]}")
with col_h2:
    st.caption(datetime.now().strftime("%H:%M:%S"))

state = load_state()
rs = state.get("robot_state", "IDLE")

steps_html = ""
for s in FLOW:
    sl = STATE_MESSAGES.get(s, s)
    done = FLOW.index(s) <= FLOW.index(rs) if rs in FLOW else False
    active = s == rs
    dot = "background:#111;" if active else ("background:#ccc;" if done else "background:#eee;")
    lbl = "color:#111;font-weight:600;" if active else "color:#aaa;"
    steps_html += (f"<div style='display:inline-flex;flex-direction:column;align-items:center;gap:3px;min-width:72px'>"
        f"<div style='width:10px;height:10px;border-radius:50%;{dot}'></div>"
        f"<span style='font-size:9px;{lbl}'>{sl}</span></div>")

st.markdown(f"<div style='background:#f7f7f7;border-radius:6px;padding:12px 16px;margin-bottom:16px;overflow-x:auto;white-space:nowrap;'><div style='display:flex;gap:4px;'>{steps_html}</div></div>", unsafe_allow_html=True)

if rs == "IDLE":
    st.markdown("<p style='color:#888;padding:2rem 0'>Waiting for patient request.</p>", unsafe_allow_html=True)
else:
    req=state.get("request","—"); risk=state.get("risk","—")
    kit=state.get("kit","—"); pid=state.get("patient_id","—")
    ts=state.get("timestamp","")
    time_str=datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else "—"
    risk_label=RISK_COLOR.get(risk,"—")

    c1,c2,c3=st.columns(3)
    with c1:
        st.metric("Patient",pid)
        st.metric("Request",req)
    with c2:
        st.metric("Risk",f"{risk_label} — {risk}")
        st.metric("Kit",kit)
    with c3:
        st.metric("Time",time_str)
        st.metric("Status",STATE_MESSAGES.get(rs,rs))

    st.divider()
    col1,col2,col3,col4=st.columns(4)

    with col1:
        if rs=="WAITING_FOR_NURSE_CONFIRMATION":
            if st.button("Release kit",use_container_width=True,type="primary"):
                prev=rs; state["robot_state"]="KIT_RELEASED"
                log_event(EventType.STATE_TRANSITION,state,prev=prev,msg="Nurse confirmed")
                save_state(state); st.rerun()
        elif rs=="VERIFYING_PATIENT":
            if st.button("Verify and dock",use_container_width=True):
                result=verify(state.get("patient_id",""),state.get("kit",""))
                if result["ok"]:
                    prev=rs; state["robot_state"]="DOCKING"
                    log_event(EventType.QR_OK,state,prev=prev,msg=result["message"])
                    save_state(state); st.rerun()
                else:
                    log_event(EventType.QR_NG,state,prev=rs,msg=result["message"])
                    state["robot_state"]="ERROR"; save_state(state); st.rerun()
        elif rs in NEXT:
            next_s=NEXT[rs]
            if st.button(f"Next: {STATE_MESSAGES.get(next_s,next_s)}",use_container_width=True):
                prev=rs; state["robot_state"]=next_s
                log_event(EventType.STATE_TRANSITION,state,prev=prev)
                if next_s=="COMPLETED":
                    log_event(EventType.COMPLETED,state,prev=prev,msg="Task completed")
                save_state(state); st.rerun()

    with col2:
        if rs=="COMPLETED":
            if st.button("Reset",use_container_width=True):
                log_event(EventType.RESET,state,prev=rs,msg="Reset")
                save_state({"request":None,"robot_state":"IDLE"}); st.rerun()

    with col3:
        if rs=="REQUEST_RECEIVED":
            if st.button("Cancel request",use_container_width=True):
                log_event(EventType.CANCEL,state,prev=rs,msg="Nurse cancelled")
                save_state({"request":None,"robot_state":"IDLE"}); st.rerun()

    with col4:
        if rs not in ["COMPLETED","ERROR","IDLE"]:
            if st.button("Emergency stop",use_container_width=True):
                log_event(EventType.EMERGENCY_STOP,state,prev=rs,msg="Emergency stop")
                state["robot_state"]="ERROR"; save_state(state); st.rerun()

    if rs=="ERROR":
        st.error("Error detected. Please confirm the situation and reset.")
        if st.button("Reset",use_container_width=True,key="reset_error"):
            log_event(EventType.RESET,state,prev=rs,msg="Reset from ERROR")
            save_state({"request":None,"robot_state":"IDLE"}); st.rerun()

st.divider()
st.markdown("#### Log")
if LOG_FILE.exists():
    with open(LOG_FILE,encoding="utf-8") as f:
        logs=json.load(f)
    if logs:
        import pandas as pd
        st.dataframe(pd.DataFrame(logs[::-1]),use_container_width=True,height=200)
    else:
        st.caption("No logs yet.")
else:
    st.caption("No logs yet.")

st.divider()
auto=st.checkbox("Auto-refresh every 3 seconds")
if auto:
    time.sleep(3); st.rerun()
