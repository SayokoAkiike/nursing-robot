import streamlit as st
import time
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.state_machine import STATE_LABELS as STATE_MESSAGES, ALLOWED_TRANSITIONS, DISPLAY_FLOW  # noqa: E402
from ui.common.style import CSS, LABELS  # noqa: E402
from ui.common import api_client  # noqa: E402

st.set_page_config(page_title=LABELS["app_nurse"], layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

RISK_COLOR = {"転倒リスクあり": "High", "要確認": "Check", "なし": "Low"}

def call_api(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        st.error(f"API error: {e}")
        return None

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## PreCare Console")
with col_h2:
    st.caption(datetime.now().strftime("%H:%M:%S"))

try:
    tasks = api_client.get_requests()
except Exception as e:
    st.error(f"Backend not reachable: {e}")
    st.stop()

if not tasks:
    st.markdown("<p style='color:#888;padding:2rem 0'>Waiting for patient request.</p>", unsafe_allow_html=True)
else:
    for task in tasks:
        rs = task.get("robot_state", "IDLE")
        request_id = task.get("request_id", "-")
        pid = task.get("patient_id", "-")
        req = task.get("request", "-")
        risk = task.get("risk", "-")
        kit = task.get("kit", "-")
        ts = task.get("timestamp", "")
        time_str = datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else "-"
        risk_label = RISK_COLOR.get(risk, "-")

        steps_html = ""
        for s in DISPLAY_FLOW:
            sl = STATE_MESSAGES.get(s, s)
            done = DISPLAY_FLOW.index(s) <= DISPLAY_FLOW.index(rs) if rs in DISPLAY_FLOW else False
            active = (s == rs)
            dot = "background:#111;" if active else ("background:#555;" if done else "background:#eee;")
            lbl = "color:#111;font-weight:600;" if active else "color:#aaa;"
            steps_html += f"<div style='display:inline-flex;flex-direction:column;align-items:center;gap:3px;min-width:72px'><div style='width:10px;height:10px;border-radius:50%;{dot}'></div><span style='font-size:9px;{lbl}'>{sl}</span></div>"

        with st.container(border=True):
            st.markdown(f"**{pid}** · {req} · {risk_label} · `{STATE_MESSAGES.get(rs, rs)}` · {time_str}")
            st.markdown(f"<div style='background:#f7f7f7;border-radius:6px;padding:8px 12px;overflow-x:auto;white-space:nowrap;'><div style='display:flex;gap:4px;'>{steps_html}</div></div>", unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if rs == "WAITING_FOR_NURSE_CONFIRMATION":
                    if st.button("Release kit", key=f"rel_{request_id}", use_container_width=True, type="primary"):
                        if call_api(api_client.transition_task, request_id, "KIT_RELEASED"):
                            st.rerun()
                elif rs == "VERIFYING_PATIENT":
                    if st.button("Verify and dock", key=f"ver_{request_id}", use_container_width=True):
                        if call_api(api_client.verify_task, request_id, pid, kit):
                            st.rerun()
                elif rs in ALLOWED_TRANSITIONS:
                    next_s = ALLOWED_TRANSITIONS[rs]
                    if st.button(f"Next: {STATE_MESSAGES.get(next_s, next_s)}", key=f"next_{request_id}", use_container_width=True):
                        if call_api(api_client.transition_task, request_id, next_s):
                            st.rerun()
            with c2:
                if rs in {"COMPLETED", "ERROR"}:
                    if st.button("Reset", key=f"reset_{request_id}", use_container_width=True):
                        if call_api(api_client.reset_task, request_id):
                            st.rerun()
            with c3:
                if rs in {"REQUEST_RECEIVED", "KIT_SELECTED"}:
                    if st.button("Cancel", key=f"cancel_{request_id}", use_container_width=True):
                        if call_api(api_client.nurse_cancel, request_id):
                            st.rerun()
            with c4:
                if rs not in {"COMPLETED", "ERROR", "IDLE"}:
                    if st.button("Emergency stop", key=f"stop_{request_id}", use_container_width=True):
                        if call_api(api_client.emergency_stop, request_id):
                            st.rerun()
            if rs == "ERROR":
                st.error("Error detected. Confirm and reset.")
        st.divider()

st.markdown("#### Log")
try:
    logs = api_client.get_logs()
except Exception:
    logs = []
if logs:
    import pandas as pd
    st.dataframe(pd.DataFrame(logs[::-1]), use_container_width=True, height=200)
else:
    st.caption("No logs yet.")
st.divider()
auto = st.checkbox("Auto-refresh every 3 seconds")
if auto:
    time.sleep(3)
    st.rerun()
