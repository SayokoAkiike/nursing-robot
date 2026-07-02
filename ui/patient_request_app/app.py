import streamlit as st
import time, sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from backend.storage import load_state
from robot_control import service
from robot_control.config import REQUEST_TYPES
from ui.common.style import CSS, LABELS

st.set_page_config(page_title=LABELS["app_patient"], layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

state = load_state()
robot_state = state.get("robot_state", "IDLE")

st.markdown("## PreCare Request")
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

    if robot_state in {"REQUEST_RECEIVED", "KIT_SELECTED"}:
        if st.button("Cancel request", use_container_width=True):
            try:
                service.cancel_request()
            except ValueError as e:
                st.error(f"Error: {e}")
                st.stop()
            st.rerun()
    else:
        st.caption("To cancel, please contact a nurse.")

    time.sleep(3)
    st.rerun()

elif robot_state == "COMPLETED":
    st.success("Assistance complete. Thank you.")
    if st.button("Back to home", use_container_width=True):
        service.reset()
        st.rerun()

elif robot_state == "ERROR":
    st.error("An error occurred. Please contact a nurse.")

else:
    st.markdown("#### Select your request")
    st.markdown(" ")

    cols = st.columns(len(REQUEST_TYPES))
    for col, (req_key, req_val) in zip(cols, REQUEST_TYPES.items()):
        with col:
            if st.button(req_val["label"], use_container_width=True, key=req_key):
                try:
                    service.create_request(req_key)
                except ValueError as e:
                    st.error(f"Error: {e}")
                    st.stop()
                st.rerun()

    st.divider()
    st.caption("Press a button to notify the nurse. The robot will begin preparation.")
