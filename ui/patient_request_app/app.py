import streamlit as st
import json, os, time, sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "shared_state.json"

sys.path.insert(0, str(ROOT_DIR))
from robot_control.logger import append_log, EventType
from ui.common.style import CSS, LABELS

st.set_page_config(page_title=LABELS["app_patient"], layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

state = load_state()
robot_state = state.get("robot_state", "IDLE")

st.markdown(f"## {LABELS[chr(39)+'app_patient'+chr(39)]}", unsafe_allow_html=False)
st.caption(LABELS["room"])
st.divider()

if robot_state not in ["IDLE", "COMPLETED", "ERROR"]:
    st.markdown(f"""
<div style="border:1px solid #d0d0d0;border-radius:8px;padding:2rem;text-align:center;background:#fafafa;">
<p style="font-size:1.3rem;font-weight:600;color:#111;margin-bottom:0.5rem">{LABELS["wait_msg_ja"]}</p>
<p style="color:#555;font-size:0.95rem;margin-bottom:1rem">{LABELS["wait_msg_en"]}</p>
<p style="color:#888;font-size:0.85rem">{LABELS["nurse_coming"]}</p>
</div>""", unsafe_allow_html=True)

    req = state.get("request", "")
    st.markdown(f"**Request:** {req}")
    st.caption(f"Status: {robot_state}")

    if robot_state == "REQUEST_RECEIVED":
        if st.button("Cancel request", use_container_width=True):
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()
    else:
        st.caption("To cancel, please contact a nurse.")

    time.sleep(3)
    st.rerun()

elif robot_state == "COMPLETED":
    st.success("Assistance complete. Thank you.")
    if st.button("Back to home", use_container_width=True):
        save_state({"request": None, "robot_state": "IDLE"})
        st.rerun()

elif robot_state == "ERROR":
    st.error("An error occurred. Please contact a nurse.")
    if st.button("Reset", use_container_width=True):
        save_state({"request": None, "robot_state": "IDLE"})
        st.rerun()

else:
    st.markdown("#### Select your request")
    st.markdown(" ")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button(LABELS["toileting"], use_container_width=True, key="toileting"):
            save_state({"request": LABELS["toileting"], "kit": "KIT_TOILETING_A",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "転倒リスクあり",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            append_log(EventType.REQUEST_CREATED, patient_id="PATIENT_A_ROOM_203",
                request=LABELS["toileting"], kit="KIT_TOILETING_A",
                next_state="REQUEST_RECEIVED", message="Patient request")
            st.rerun()

    with col2:
        if st.button(LABELS["water"], use_container_width=True, key="water"):
            save_state({"request": LABELS["water"], "kit": "KIT_WATER",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "なし",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            append_log(EventType.REQUEST_CREATED, patient_id="PATIENT_A_ROOM_203",
                request=LABELS["water"], kit="KIT_WATER",
                next_state="REQUEST_RECEIVED", message="Patient request")
            st.rerun()

    with col3:
        if st.button(LABELS["nurse_check"], use_container_width=True, key="nurse_check"):
            save_state({"request": LABELS["nurse_check"], "kit": "ALERT_NURSE_ONLY",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "要確認",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            append_log(EventType.REQUEST_CREATED, patient_id="PATIENT_A_ROOM_203",
                request=LABELS["nurse_check"], kit="ALERT_NURSE_ONLY",
                next_state="REQUEST_RECEIVED", message="Patient request")
            st.rerun()

    st.divider()
    st.caption("Press a button to notify the nurse. The robot will begin preparation.")
