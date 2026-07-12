import streamlit as st
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.config import REQUEST_TYPES, DEFAULT_PATIENT_ID, PATIENTS  # noqa: E402
from ui.common.style import CSS, LABELS  # noqa: E402
from ui.common import api_client  # noqa: E402

# Demo deployment (Streamlit Community Cloud): this file is reused as-is by
# pages/1_患者用タブレット.py, which imports main() and calls it explicitly on
# every rerun rather than relying on import side effects (a plain module
# import only executes top-level code once per Python process, which would
# break Streamlit's per-rerun re-render model on the second navigation to
# the page). Wrapping everything in main() + the __main__ guard below keeps
# `streamlit run ui/patient_request_app/app.py` working exactly as before
# for local/Codespaces use -- this is purely a reuse-enabling refactor, no
# behavior change.
REFRESH_INTERVAL_SECONDS = 2


def main() -> None:
    st.set_page_config(page_title=LABELS["app_patient"], layout="centered")
    st.markdown(CSS, unsafe_allow_html=True)

    patient_id = st.query_params.get("patient_id", DEFAULT_PATIENT_ID)

    st.markdown("## PreCare Request")
    p_info = PATIENTS.get(patient_id, {})
    st.caption(f"Room {p_info.get('room', '?')} — {p_info.get('display_name', patient_id)}")
    st.divider()

    # Item 6 (realtime UI upgrade): this whole screen used to hand-roll its own
    # polling with `time.sleep(3); st.rerun()`, which blocks the entire script
    # for 3s and then re-runs and re-fetches everything from scratch -- while
    # waiting, that's the *only* thing on the page, so it was mostly harmless
    # here, but it's the same pattern the nurse dashboard used everywhere, and
    # it meant this screen could never move itself from "select a request" to
    # "waiting" (or from "waiting" to "assistance complete") without that
    # explicit sleep/rerun, i.e. it wasn't actually reactive to state changes
    # that happen for reasons other than this patient's own button clicks (a
    # nurse resetting the task, a rounding escalation coming in). Wrapping the
    # whole screen in one `st.experimental_fragment(run_every=...)` fragment
    # makes it re-check the backend on a fixed interval and re-render whichever
    # of the three screens (select / waiting / done) currently applies, without
    # a blocking sleep call and without the caller having to reason about which
    # branch needs a rerun -- the fragment just re-decides from scratch each
    # time, exactly like a fresh page load would, but without an actual reload.
    @st.experimental_fragment(run_every=REFRESH_INTERVAL_SECONDS)
    def render_patient_screen():
        try:
            tasks = api_client.get_requests()
        except Exception as e:
            st.error(f"Backend not reachable: {e}")
            return

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

        if my_escalation:
            st.markdown(f'''<div style="border:1px solid #d0d0d0;border-radius:8px;padding:2rem;text-align:center;background:#fafafa;">
<p style="font-size:1.1rem;font-weight:600">{LABELS["escalation_notified"]}</p>
<p style="font-size:1.3rem;font-weight:600">{LABELS["wait_msg_ja"]}</p>
<p style="color:#555">{LABELS["wait_msg_en"]}</p>
<p style="color:#888">{LABELS["nurse_coming"]}</p></div>''', unsafe_allow_html=True)
        elif my_task:
            robot_state = my_task.get("robot_state", "IDLE")
            request_id = my_task.get("request_id", "")
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
                            return
                        st.rerun()
                else:
                    st.caption("To cancel, please contact a nurse.")
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
                            return
                        st.rerun()
            st.divider()
            st.caption("Press a button to notify the nurse. The robot will begin preparation.")

    render_patient_screen()


if __name__ == "__main__":
    main()
