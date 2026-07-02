import streamlit as st
import json, time, sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.state_machine import STATE_LABELS as STATE_MESSAGES, ALLOWED_TRANSITIONS, DISPLAY_FLOW
from robot_control import service
from backend.storage import load_state, load_logs
from ui.common.style import CSS, LABELS

st.set_page_config(page_title=LABELS["app_nurse"], layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

def log_and_rerun(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except ValueError as e:
        st.error(f"Error: {e}")
    st.rerun()

state = load_state()
rs = state.get("robot_state", "IDLE")

col_h1, col_h2 = st.columns([3,1])
with col_h1:
    st.markdown("## PreCare Console")
with col_h2:
    st.caption(datetime.now().strftime("%H:%M:%S"))

steps_html = ""
for s in DISPLAY_FLOW:
    sl = STATE_MESSAGES.get(s, s)
    done = DISPLAY_FLOW.index(s) <= DISPLAY_FLOW.index(rs) if rs in DISPLAY_FLOW else False
    active = s == rs
    dot = "background:#111;" if active else ("background:#ccc;" if done else "background:#eee;")
    lbl = "color:#111;font-weight:600;" if active else "color:#aaa;"
    steps_html += (f"<div style='display:inline-flex;flex-direction:column;align-items:center;gap:3px;min-width:72px'>"        f"<div style='width:10px;height:10px;border-radius:50%;{dot}'></div>"        f"<span style='font-size:9px;{lbl}'>{sl}</span></div>")

st.markdown(f"<div style='background:#f7f7f7;border-radius:6px;padding:12px 16px;margin-bottom:16px;overflow-x:auto;white-space:nowrap;'><div style='display:flex;gap:4px;'>{steps_html}</div></div>", unsafe_allow_html=True)

RISK_COLOR = {"転倒リスクあり": "High", "要確認": "Check", "なし": "Low"}

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
                log_and_rerun(service.advance_state, "KIT_RELEASED")
        elif rs=="VERIFYING_PATIENT":
            if st.button("Verify and dock",use_container_width=True):
                result = service.verify_ids(pid, kit)
                if not result.get("ok", True):
                    st.error("QR verification failed")
                st.rerun()
        elif rs in ALLOWED_TRANSITIONS:
            next_s=ALLOWED_TRANSITIONS[rs]
            if st.button(f"Next: {STATE_MESSAGES.get(next_s,next_s)}",use_container_width=True):
                log_and_rerun(service.advance_state, next_s)

    with col2:
        if rs=="COMPLETED":
            if st.button("Reset",use_container_width=True):
                log_and_rerun(service.reset)

    with col3:
        if rs=="REQUEST_RECEIVED":
            if st.button("Cancel request",use_container_width=True):
                log_and_rerun(service.cancel_request)

    with col4:
        if rs not in ["COMPLETED","ERROR","IDLE"]:
            if st.button("Emergency stop",use_container_width=True):
                log_and_rerun(service.emergency_stop)

    if rs=="ERROR":
        st.error("Error detected. Please confirm the situation and reset.")
        if st.button("Reset",use_container_width=True,key="reset_error"):
            log_and_rerun(service.reset)

st.divider()
st.markdown("#### Log")
logs = load_logs()
if logs:
    import pandas as pd
    st.dataframe(pd.DataFrame(logs[::-1]),use_container_width=True,height=200)
else:
    st.caption("No logs yet.")

st.divider()
auto=st.checkbox("Auto-refresh every 3 seconds")
if auto:
    time.sleep(3); st.rerun()
