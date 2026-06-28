import streamlit as st
import json, os, time, sys
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

st.set_page_config(page_title="看護師ダッシュボード", page_icon="👩‍⚕️", layout="wide")

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def log_event(event_type, s, prev=None, msg=""):
    append_log(
        event_type=event_type,
        patient_id=s.get("patient_id", "—"),
        request=s.get("request", "—"),
        kit=s.get("kit", "—"),
        previous_state=prev or "—",
        next_state=s.get("robot_state", "—"),
        result="OK" if "ERROR" not in s.get("robot_state", "") else "NG",
        message=msg,
    )

COLORS = {
    "IDLE": "#6b7280", "REQUEST_RECEIVED": "#f59e0b", "KIT_SELECTED": "#f59e0b",
    "MOVING_TO_BEDSIDE": "#3b82f6", "VERIFYING_PATIENT": "#8b5cf6", "DOCKING": "#8b5cf6",
    "TRAY_LIFTING": "#06b6d4", "WAITING_FOR_NURSE_CONFIRMATION": "#f97316",
    "KIT_RELEASED": "#10b981", "COMPLETED": "#10b981", "ERROR": "#ef4444",
}
ICONS = {
    "IDLE": "⬜", "REQUEST_RECEIVED": "🔔", "KIT_SELECTED": "📦",
    "MOVING_TO_BEDSIDE": "🚗", "VERIFYING_PATIENT": "🔍", "DOCKING": "🔗",
    "TRAY_LIFTING": "⬆️", "WAITING_FOR_NURSE_CONFIRMATION": "⏳",
    "KIT_RELEASED": "✅", "COMPLETED": "🎉", "ERROR": "🚨",
}
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
RISK_COLOR = {"転倒リスクあり": "🔴", "要確認": "🟡", "なし": "🟢"}

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## 👩‍⚕️ 看護師ダッシュボード")
with col_h2:
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

state = load_state()
rs = state.get("robot_state", "IDLE")
icon = ICONS.get(rs, "❓")
color = COLORS.get(rs, "#6b7280")

steps_html = ""
for s in FLOW:
    sc = COLORS.get(s, "#6b7280")
    sl = STATE_MESSAGES.get(s, s)
    done = FLOW.index(s) <= FLOW.index(rs) if rs in FLOW else False
    active = s == rs
    dot = f"background:{sc};" if done else "background:#e5e7eb;"
    lbl = f"color:{sc};font-weight:600;" if active else "color:#9ca3af;"
    steps_html += (
        f"<div style='display:inline-flex;flex-direction:column;"
        f"align-items:center;gap:4px;min-width:60px'>"
        f"<div style='width:14px;height:14px;border-radius:50%;{dot}'></div>"
        f"<span style='font-size:10px;{lbl}'>{sl}</span></div>"
    )

st.markdown(
    f"<div style='background:#f9fafb;border-radius:12px;padding:14px 20px;"
    f"margin-bottom:20px;overflow-x:auto;white-space:nowrap;'>"
    f"<div style='display:flex;gap:6px;'>{steps_html}</div></div>",
    unsafe_allow_html=True,
)

if rs == "IDLE":
    st.info("🟢 患者からのリクエストを待っています")
else:
    req = state.get("request", "—")
    risk = state.get("risk", "—")
    kit = state.get("kit", "—")
    pid = state.get("patient_id", "—")
    ts = state.get("timestamp", "")
    time_str = datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else "—"
    risk_icon = RISK_COLOR.get(risk, "⚪")

    st.markdown(f"### {icon} {STATE_MESSAGES.get(rs, rs)}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("患者ID", pid)
        st.metric("リクエスト", req)
    with c2:
        st.metric("リスク", f"{risk_icon} {risk}")
        st.metric("キット", kit)
    with c3:
        st.metric("時刻", time_str)

    st.divider()
    st.markdown("#### 🎮 操作")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if rs == "WAITING_FOR_NURSE_CONFIRMATION":
            if st.button("✅ キットを開放する", use_container_width=True, type="primary"):
                prev = rs
                state["robot_state"] = "KIT_RELEASED"
                log_event(EventType.STATE_TRANSITION, state, prev=prev, msg="看護師がキット開放確認")
                save_state(state)
                st.rerun()
        elif rs == "VERIFYING_PATIENT":
            if st.button("🔍 QR照合してDOCKING", use_container_width=True):
                result = verify(state.get("patient_id", ""), state.get("kit", ""))
                if result["ok"]:
                    prev = rs
                    state["robot_state"] = "DOCKING"
                    log_event(EventType.QR_OK, state, prev=prev, msg=result["message"])
                    save_state(state)
                    st.success("✅ 照合OK")
                    st.rerun()
                else:
                    log_event(EventType.QR_NG, state, prev=rs, msg=result["message"])
                    state["robot_state"] = "ERROR"
                    save_state(state)
                    st.error(f"❌ {result['message']}")
                    st.rerun()
        elif rs in NEXT:
            next_s = NEXT[rs]
            if st.button(f"▶ 次へ：{STATE_MESSAGES.get(next_s, next_s)}", use_container_width=True):
                prev = rs
                state["robot_state"] = next_s
                log_event(EventType.STATE_TRANSITION, state, prev=prev)
                if next_s == "COMPLETED":
                    log_event(EventType.COMPLETED, state, prev=prev, msg="タスク完了")
                save_state(state)
                st.rerun()

    with col2:
        if rs == "COMPLETED":
            if st.button("🔄 次のリクエストへ", use_container_width=True):
                log_event(EventType.RESET, state, prev=rs, msg="リセット")
                save_state({"request": None, "robot_state": "IDLE"})
                st.rerun()

    with col3:
        if rs == "REQUEST_RECEIVED":
            if st.button("✖ リクエスト取り消し", use_container_width=True):
                log_event(EventType.CANCEL, state, prev=rs, msg="看護師がキャンセル")
                save_state({"request": None, "robot_state": "IDLE"})
                st.rerun()

    with col4:
        if rs not in ["COMPLETED", "ERROR", "IDLE"]:
            if st.button("🛑 緊急停止", use_container_width=True):
                log_event(EventType.EMERGENCY_STOP, state, prev=rs, msg="緊急停止")
                state["robot_state"] = "ERROR"
                save_state(state)
                st.rerun()

    if rs == "ERROR":
        st.error("🚨 エラー発生。確認後にリセットしてください。")
        if st.button("🔄 リセット", use_container_width=True):
            log_event(EventType.RESET, state, prev=rs, msg="ERRORからリセット")
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()

st.divider()
st.markdown("#### 📜 動作ログ")
if LOG_FILE.exists():
    with open(LOG_FILE, encoding="utf-8") as f:
        logs = json.load(f)
    if logs:
        import pandas as pd
        st.dataframe(pd.DataFrame(logs[::-1]), use_container_width=True, height=200)
    else:
        st.caption("まだログがありません")
else:
    st.caption("まだログがありません")

st.divider()
auto = st.checkbox("⏱ 3秒ごとに自動更新")
if auto:
    time.sleep(3)
    st.rerun()
