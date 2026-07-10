import streamlit as st
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from robot_control.state_machine import STATE_LABELS as STATE_MESSAGES, ALLOWED_TRANSITIONS, DISPLAY_FLOW  # noqa: E402
from ui.common.style import CSS, LABELS, PRIORITY_COLOR  # noqa: E402
from ui.common import api_client  # noqa: E402

st.set_page_config(page_title=LABELS["app_nurse"], layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

RISK_COLOR = {"転倒リスクあり": "High", "要確認": "Check", "なし": "Low"}

# Item 6 (realtime UI upgrade): every section below used to only refresh via
# a manual "Auto-refresh every 3 seconds" checkbox that, when on, blocked the
# *entire* script for 3s (time.sleep) and then re-ran and re-rendered the
# whole page (st.rerun()) -- escalations, tasks, and the log together, even
# if only one of them had actually changed. `st.experimental_fragment`
# (stable `st.fragment` doesn't exist yet on the pinned streamlit==1.35.0;
# this is the pre-1.37 name for the same feature) lets each section
# independently re-run and redraw on its own timer without blocking or
# re-rendering the other two, and without a manual opt-in checkbox. This is
# a genuine reduction in staleness (always-on vs. opt-in) and in per-refresh
# cost (one section's dataframe re-render doesn't force the others to
# re-render too), while staying inside vanilla Streamlit (no new
# dependencies, no custom WebSocket client thread fighting Streamlit's
# script-rerun model).
REFRESH_INTERVAL_SECONDS = 2


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


# ---------------------------------------------------------------------------
# PR26: Escalations section -- the queue of things a nurse needs to see/ack,
# raised by a rounding session (backend/services/rounding_service.py /
# escalation_service.py). Deliberately shown as its own section, separate
# from the delivery task list below (proposal doc: "既存のタスク一覧とは別に、
# 「看護師が見るべき通知キュー」として表示したい"), and placed above it so a
# HIGH/URGENT notification isn't buried under in-progress deliveries.
# ---------------------------------------------------------------------------
@st.experimental_fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_escalations():
    st.markdown(f"### {LABELS['escalations_title']}")
    try:
        escalations = api_client.get_escalations()
    except Exception as e:
        st.error(f"Backend not reachable: {e}")
        return

    if not escalations:
        st.caption(LABELS["escalations_empty"])
        return

    for esc in escalations:
        priority = esc.get("priority", "LOW")
        color = PRIORITY_COLOR.get(priority, PRIORITY_COLOR["LOW"])
        status = esc.get("status", "PENDING")
        esc_id = esc.get("id", "-")
        created_at = esc.get("created_at", "")
        time_str = datetime.fromisoformat(created_at).strftime("%H:%M:%S") if created_at else "-"

        with st.container(border=True):
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;'>"
                f"<span style='background:{color};color:#fff;border-radius:4px;"
                f"padding:2px 8px;font-size:12px;font-weight:700;'>{priority}</span>"
                f"<span style='font-weight:600;'>Room {esc.get('room', '-')}</span>"
                f"<span style='color:#888;'>{esc.get('patient_id', '-')}</span>"
                f"<span style='color:#888;margin-left:auto;'>{time_str} · {status}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"{esc.get('summary', '')}")
            if esc.get("suggested_action"):
                st.caption(f"Suggested action: {esc['suggested_action']}")
            escalated_count = esc.get("escalated_count") or 0
            if escalated_count:
                st.caption(f"⚠️ 未確認のため優先度を自動引き上げ済み（{escalated_count}回）")
            if status == "PENDING":
                if st.button(
                    LABELS["ack_button"], key=f"ack_{esc_id}", use_container_width=False
                ):
                    if call_api(api_client.acknowledge_escalation, esc_id, "nurse_dashboard"):
                        st.rerun()


@st.experimental_fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_tasks():
    try:
        tasks = api_client.get_requests()
    except Exception as e:
        st.error(f"Backend not reachable: {e}")
        return

    if not tasks:
        st.markdown("<p style='color:#888;padding:2rem 0'>Waiting for patient request.</p>", unsafe_allow_html=True)
        return

    for task in tasks:
        rs = task.get("robot_state", "IDLE")
        request_id = task.get("request_id", "-")
        pid = task.get("patient_id", "-")
        req = task.get("request", "-")
        risk = task.get("risk", "-")
        kit = task.get("kit", "-")
        # Item 5 (multi-robot support): workflow_service._view() now
        # includes robot_id, so a nurse watching several robots at once
        # can tell which robot each task belongs to instead of assuming
        # it's always the one robot the dashboard used to imply.
        robot_id = task.get("robot_id", "-")
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
            st.markdown(f"**{pid}** · {req} · {risk_label} · `{STATE_MESSAGES.get(rs, rs)}` · {robot_id} · {time_str}")
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


@st.experimental_fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_log():
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


render_escalations()
st.divider()
render_tasks()
render_log()
