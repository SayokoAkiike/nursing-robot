import streamlit as st
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.config import REQUEST_TYPES, DEFAULT_PATIENT_ID, PATIENTS  # noqa: E402
from ui.common.style import CSS, LABELS  # noqa: E402
from ui.common import api_client  # noqa: E402

st.set_page_config(page_title=LABELS["app_patient"], layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

patient_id = st.query_params.get("patient_id", DEFAULT_PATIENT_ID)

try:
    tasks = api_client.get_requests()
except Exception as e:
    st.error(f"Backend not reachable: {e}")
    st.stop()

my_task = next((t for t in tasks if t.get("patient_id") == patient_id), None)

# PR26: a rounding session (backend/services/rounding_service.py) can
# raise a nurse escalation for this patient independent of any
# care_request the patient-tablet flow tracks -- e.g. the robot heard
# "トイレに行きたいです" during rounding and is now waiting on a nurse,
# with no delivery request involved at all. Checked before the existing
# my_task branch below so the safety notice ("立ち上がらずお待ちください")
# shows regardless of whether a delivery task also happens to be active.
try:
    pending_escalations = api_client.get_escalations(status="PENDING")
except Exception:
    pending_escalations = []
my_escalation = next(
    (e for e in pending_escalations if e.get("patient_id") == patient_id), None
)

st.markdown("## PreCare Request")
p_info = PATIENTS.get(patient_id, {})
st.caption(f"Room {p_info.get('room', '?')} — {p_info.get('display_name', patient_id)}")
st.divider()

if my_escalation:
    st.markdown(f'''<div style="border:1px solid #d0d0d0;border-radius:8px;padding:2rem;text-align:center;background:#fafafa;">
<p style="font-size:1.1rem;font-weight:600">{LABELS["escalation_notified"]}</p>
<p style="font-size:1.3rem;font-weight:600">{LABELS["wait_msg_ja"]}</p>
<p style="color:#555">{LABELS["wait_msg_en"]}</p>
<p style="color:#888">{LABELS["nurse_coming"]}</p></div>''', unsafe_allow_html=True)
    time.sleep(3)
    st.rerun()
elif my_task:
    robot_state = my_task.get("robot_state", "IDLE")
    request_id  = my_task.get("request_id", "")
    if robot_state not in ["IDLE", "COMPLETED", "ERROR"]:
        st.markdown(f'''<div style="border:1px solid #d0d0d0;border-radius:8px;padding:2rem;text-align:center;background:#fafafa;">
<p style="font-size:1.3rem;font-weight:600">{LABELS["wait_msg_ja"]}</p>
<p style="color:#555">{LABELS["wait_msg_en"]}</p>
<p style="color:#888">{LABELS["nurse_coming"]}</p></div>''', unsafe_allow_html=True)
        st.markdown(f"**Request:** {my_task.get('request', '')}")
        st.caption(f"Status: {robot_state}")
        if robot_state in {"REQUEST_RECEIVED", "KIT_SELECTED"}:
            if st.button("Cancel request", use_container_width=True):
                try:
                    api_client.cancel_request(request_id)
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.stop()
                st.rerun()
        else:
            st.caption("To cancel, please contact a nurse.")
        time.sleep(3)
        st.rerun()
    elif robot_state == "COMPLETED":
        st.success("Assistance complete. Thank you.")
    elif robot_state == "ERROR":
        st.error("An error occurred. Please contact a nurse.")
else:
    st.markdown("#### Select your request")
    cols = st.columns(len(REQUEST_TYPES))
    for col, (req_key, req_val) in zip(cols, REQUEST_TYPES.items()):
        with col:
            if st.button(req_val["label"], use_container_width=True, key=req_key):
                try:
                    api_client.create_request(patient_id, req_key)
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.stop()
                st.rerun()
    st.divider()
    st.caption("Press a button to notify the nurse. The robot will begin preparation.")
