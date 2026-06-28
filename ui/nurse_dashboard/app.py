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

FLOW = [
    "REQUEST_RECEIVED", "KIT_SELECTED", "MOVING_TO_BEDSIDE",
    "VERIFYING_PATIENT", "DOCKING", "TRAY_LIFTING",
    "WAITING_FOR_NURSE_CONFIRMATION", "KIT_RELEASED", "COMPLETED",
]

RISK_COLOR = {"転倒リスクあり": "🔴", "要確認": "🟡", "なし": "🟢"}

# ── ヘッダー ──
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## 👩‍⚕️ 看護師ダッシュボード")
with col_h2:
    st.caption(f"🕐 {datetime.now().strftime('%H:%M:%S')}")

state = load_state()
rs = state.get("robot_state", "IDLE")
icon, label, color = STATES.get(rs, ("❓", rs, "#6b7280"))

# ── 進捗バー（Streamlitネイティブで描画）──
st.markdown("##### 進捗")
cols = st.columns(len(FLOW))
for i, s in enumerate(FLOW):
    si, sl, sc = STATES[s]
    done   = FLOW.index(s) <= FLOW.index(rs) if rs in FLOW else False
    active = s == rs
    with cols[i]:
        if active:
            st.markdown(f"<div style='text-align:center; color:{sc}; font-weight:bold; font-size:11px'>{si}<br>{sl}</div>", unsafe_allow_html=True)
        elif done:
            st.markdown(f"<div style='text-align:center; color:{sc}; font-size:11px'>{si}<br>{sl}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:center; color:#d1d5db; font-size:11px'>○<br>{sl}</div>", unsafe_allow_html=True)

st.divider()

# ── IDLE のとき ──
if rs == "IDLE":
    st.info("🟢 患者からのリクエストを待っています")

else:
    req      = state.get("request", "—")
    risk     = state.get("risk", "—")
    kit      = state.get("kit", "—")
    pid      = state.get("patient_id", "—")
    ts       = state.get("timestamp", "")
    time_str = datetime.fromisoformat(ts).strftime("%H:%M:%S") if ts else "—"
    risk_icon = RISK_COLOR.get(risk, "⚪")

    # ── リクエスト詳細 ──
    st.markdown(f"### {icon} {label}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("患者ID", pid)
        st.metric("リクエスト", req)
    with col2:
        st.metric("リスク", f"{risk_icon} {risk}")
        st.metric("必要キット", kit)
    with col3:
        st.metric("リクエスト時刻", time_str)

    st.divider()

    # ── 操作ボタン ──
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

# ── ログ ──
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

# ── 自動更新 ──
st.divider()
auto = st.checkbox("⏱ 3秒ごとに自動更新")
if auto:
    time.sleep(3)
    st.rerun()
