"""
看護師ダッシュボード
実行方法: python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
"""

import streamlit as st
import json, os, time
from datetime import datetime

st.set_page_config(page_title="看護師ダッシュボード", page_icon="👩‍⚕️", layout="wide")

STATE_FILE = "shared_state.json"
LOG_FILE   = "robot_log.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def append_log(s):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    logs.append({
        "時刻":       datetime.now().strftime("%H:%M:%S"),
        "患者ID":     s.get("patient_id", "—"),
        "リクエスト": s.get("request", "—"),
        "キット":     s.get("kit", "—"),
        "結果":       s.get("robot_state", "—"),
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

STATES = {
    "IDLE":                           ("⬜", "待機中",        "#6b7280"),
    "REQUEST_RECEIVED":               ("🔔", "リクエスト受信", "#f59e0b"),
    "KIT_SELECTED":                   ("📦", "キット選択中",   "#f59e0b"),
    "MOVING_TO_BEDSIDE":              ("🚗", "移動中",         "#3b82f6"),
    "VERIFYING_PATIENT":              ("🔍", "ID照合中",       "#8b5cf6"),
    "DOCKING":                        ("🔗", "ドッキング中",   "#8b5cf6"),
    "TRAY_LIFTING":                   ("⬆️",  "トレイ上昇中",  "#06b6d4"),
    "WAITING_FOR_NURSE_CONFIRMATION": ("⏳", "確認待ち",       "#f97316"),
    "KIT_RELEASED":                   ("✅", "キット開放",     "#10b981"),
    "COMPLETED":                      ("🎉", "完了",           "#10b981"),
    "ERROR":                          ("🚨", "エラー",         "#ef4444"),
}

NEXT = {
    "REQUEST_RECEIVED":               "KIT_SELECTED",
    "KIT_SELECTED":                   "MOVING_TO_BEDSIDE",
    "MOVING_TO_BEDSIDE":              "VERIFYING_PATIENT",
    "VERIFYING_PATIENT":              "DOCKING",
    "DOCKING":                        "TRAY_LIFTING",
    "TRAY_LIFTING":                   "WAITING_FOR_NURSE_CONFIRMATION",
    "WAITING_FOR_NURSE_CONFIRMATION": "KIT_RELEASED",
    "KIT_RELEASED":                   "COMPLETED",
}

RISK_COLOR = {"転倒リスクあり": "🔴", "要確認": "🟡", "なし": "🟢"}

st.markdown("""
<style>
.state-card {
    border-radius: 14px; padding: 18px 22px;
    margin-bottom: 16px; border: 1.5px solid #e5e7eb;
    background: white;
}
.state-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-size: 13px; font-weight: 600;
}
.progress-step {
    display: inline-flex; flex-direction: column; align-items: center;
    font-size: 11px; gap: 4px; min-width: 60px;
}
.step-dot { width: 14px; height: 14px; border-radius: 50%; }
</style>
""", unsafe_allow_html=True)

col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## 👩‍⚕️ 看護師ダッシュボード")
with col_h2:
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

state = load_state()
rs = state.get("robot_state", "IDLE")
icon, label, color = STATES.get(rs, ("❓", rs, "#6b7280"))

FLOW = [
    "REQUEST_RECEIVED", "KIT_SELECTED", "MOVING_TO_BEDSIDE",
    "VERIFYING_PATIENT", "DOCKING", "TRAY_LIFTING",
    "WAITING_FOR_NURSE_CONFIRMATION", "KIT_RELEASED", "COMPLETED",
]

steps_html = ""
for s in FLOW:
    si, sl, sc = STATES[s]
    done   = FLOW.index(s) <= FLOW.index(rs) if rs in FLOW else False
    active = s == rs
    dot_style   = f"background:{sc};" if done else "background:#e5e7eb;"
    label_style = f"color:{sc}; font-weight:600;" if active else "color:#9ca3af;"
    steps_html += f"""
    <div class="progress-step">
        <div class="step-dot" style="{dot_style}"></div>
        <span style="font-size:10px; {label_style}">{sl}</span>
    </div>"""

st.markdown(f"""
<div style="background:#f9fafb; border-radius:12px; padding:14px 20px;
margin-bottom:20px; overflow-x:auto; white-space:nowrap;">
<div style="display:flex; gap:6px; align-items:flex-start; justify-content:space-between;">
{steps_html}
</div>
</div>
""", unsafe_allow_html=True)

if rs == "IDLE":
    st.markdown("""
    <div style="text-align:center; padding:48px; color:#9ca3af; font-size:18px;">
        🟢　患者からのリクエストを待っています
    </div>
    """, unsafe_allow_html=True)

else:
    req      = state.get("request", "—")
    risk     = state.get("risk", "—")
    kit      = state.get("kit", "—")
    pid      = state.get("patient_id", "—")
    ts       = state.get("timestamp", "")
    time_str = datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else "—"
    risk_icon = RISK_COLOR.get(risk, "⚪")

    st.markdown(f"""
    <div class="state-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
            <span style="font-size:17px; font-weight:600">📋 現在のリクエスト</span>
            <span class="state-badge" style="background:{color}22; color:{color}; border:1px solid {color}66">
                {icon} {label}
            </span>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; font-size:14px;">
            <div><span style="color:#6b7280">患者ID</span><br><b>{pid}</b></div>
            <div><span style="color:#6b7280">リクエスト時刻</span><br><b>{time_str}</b></div>
            <div><span style="color:#6b7280">リクエスト内容</span><br><b>{req}</b></div>
            <div><span style="color:#6b7280">リスク</span><br><b>{risk_icon} {risk}</b></div>
            <div><span style="color:#6b7280">必要キット</span><br><b>{kit}</b></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🎮 操作")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if rs == "WAITING_FOR_NURSE_CONFIRMATION":
            if st.button("✅ キットを開放する", use_container_width=True, type="primary"):
                state["robot_state"] = "KIT_RELEASED"
                save_state(state)
                st.rerun()
        elif rs in NEXT:
            _, next_label, _ = STATES[NEXT[rs]]
            if st.button(f"▶ 次へ：{next_label}", use_container_width=True):
                state["robot_state"] = NEXT[rs]
                if NEXT[rs] == "COMPLETED":
                    append_log(state)
                save_state(state)
                st.rerun()

    with col2:
        if rs == "COMPLETED":
            if st.button("🔄 次のリクエストへ", use_container_width=True):
                save_state({"request": None, "robot_state": "IDLE"})
                st.rerun()

    with col3:
        if rs == "REQUEST_RECEIVED":
            if st.button("✖ リクエスト取り消し", use_container_width=True):
                save_state({"request": None, "robot_state": "IDLE"})
                st.rerun()

    with col4:
        if rs not in ["COMPLETED", "ERROR", "IDLE"]:
            if st.button("🛑 緊急停止", use_container_width=True):
                state["robot_state"] = "ERROR"
                save_state(state)
                st.rerun()

    if rs == "ERROR":
        st.error("🚨 エラー発生。確認後にリセットしてください。")
        if st.button("🔄 リセット", use_container_width=True):
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()

st.divider()
st.markdown("#### 📜 動作ログ")

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
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
