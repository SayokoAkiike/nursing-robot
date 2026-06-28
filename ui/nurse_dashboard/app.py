"""
看護師ダッシュボード (Day 6)
実行方法: streamlit run ui/nurse_dashboard/app.py --server.port 8502
"""

import streamlit as st
import json
import os
from datetime import datetime

# ── ページ設定 ───────────────────────────────────────
st.set_page_config(
    page_title="看護師ダッシュボード",
    page_icon="👩‍⚕️",
    layout="wide",
)

STATE_FILE = "shared_state.json"
LOG_FILE = "robot_log.json"

# ── 状態ファイル操作 ──────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def append_log(state: dict):
    logs = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "patient_id": state.get("patient_id", "—"),
        "request": state.get("request", "—"),
        "kit": state.get("kit", "—"),
        "result": state.get("robot_state", "—"),
    })
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# ── 状態バッジ ────────────────────────────────────────
STATE_LABELS = {
    "IDLE":                        ("⬜", "待機中"),
    "REQUEST_RECEIVED":            ("🔔", "リクエスト受信"),
    "KIT_SELECTED":                ("📦", "キット選択中"),
    "MOVING_TO_BEDSIDE":           ("🤖", "移動中"),
    "VERIFYING_PATIENT":           ("🔍", "ID照合中"),
    "DOCKING":                     ("🔗", "ドッキング中"),
    "TRAY_LIFTING":                ("⬆️", "トレイ上昇中"),
    "WAITING_FOR_NURSE_CONFIRMATION": ("⏳", "看護師確認待ち"),
    "KIT_RELEASED":                ("✅", "キット開放済み"),
    "COMPLETED":                   ("🎉", "完了"),
    "ERROR":                       ("🚨", "エラー"),
}

RISK_COLORS = {
    "転倒リスクあり": "🔴",
    "要確認": "🟡",
    "なし": "🟢",
}

# ── ヘッダー ─────────────────────────────────────────
st.title("👩‍⚕️ 看護師ダッシュボード")
st.caption(f"最終更新：{datetime.now().strftime('%H:%M:%S')}")

state = load_state()
robot_state = state.get("robot_state", "IDLE")

# ── 上段：ロボット状態サマリー ────────────────────────
col1, col2, col3 = st.columns(3)

icon, label = STATE_LABELS.get(robot_state, ("❓", robot_state))
with col1:
    st.metric("🤖 ロボット状態", f"{icon} {label}")

with col2:
    req = state.get("request", "—")
    st.metric("📋 リクエスト", req if req else "—")

with col3:
    risk = state.get("risk", "—")
    risk_icon = RISK_COLORS.get(risk, "⚪")
    st.metric("⚠️ リスク", f"{risk_icon} {risk}")

st.divider()

# ── 中段：リクエスト詳細 ──────────────────────────────
if robot_state != "IDLE":
    st.subheader("📋 現在のリクエスト詳細")

    col_a, col_b = st.columns(2)
    with col_a:
        st.write(f"**患者ID：** {state.get('patient_id', '—')}")
        st.write(f"**リクエスト：** {state.get('request', '—')}")
        st.write(f"**必要キット：** {state.get('kit', '—')}")

    with col_b:
        ts = state.get("timestamp")
        if ts:
            dt = datetime.fromisoformat(ts)
            st.write(f"**リクエスト時刻：** {dt.strftime('%H:%M:%S')}")
        st.write(f"**ロボット状態：** {icon} {label}")

    st.divider()

    # ── ロボット操作ボタン ────────────────────────────
    st.subheader("🎮 ロボット操作")

    # 状態を一歩進めるデモ用ボタン
    NEXT_STATE = {
        "REQUEST_RECEIVED":            "KIT_SELECTED",
        "KIT_SELECTED":                "MOVING_TO_BEDSIDE",
        "MOVING_TO_BEDSIDE":           "VERIFYING_PATIENT",
        "VERIFYING_PATIENT":           "DOCKING",
        "DOCKING":                     "TRAY_LIFTING",
        "TRAY_LIFTING":                "WAITING_FOR_NURSE_CONFIRMATION",
        "WAITING_FOR_NURSE_CONFIRMATION": "KIT_RELEASED",
        "KIT_RELEASED":                "COMPLETED",
    }

    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if robot_state in NEXT_STATE:
            next_s = NEXT_STATE[robot_state]
            next_icon, next_label = STATE_LABELS.get(next_s, ("", next_s))
            if st.button(f"▶️ 次へ進む\n→ {next_label}", use_container_width=True):
                state["robot_state"] = next_s
                if next_s == "COMPLETED":
                    append_log(state)
                save_state(state)
                st.rerun()

    with col_btn2:
        if robot_state == "WAITING_FOR_NURSE_CONFIRMATION":
            if st.button("✅ 確認・キット開放", use_container_width=True, type="primary"):
                state["robot_state"] = "KIT_RELEASED"
                save_state(state)
                st.rerun()

    with col_btn3:
        if st.button("🛑 緊急停止", use_container_width=True):
            state["robot_state"] = "ERROR"
            save_state(state)
            st.rerun()

    if robot_state == "COMPLETED":
        if st.button("🔄 リセット（次のリクエストへ）", use_container_width=True):
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()

else:
    st.info("🟢 ロボット待機中 — 患者からのリクエストをお待ちしています")

st.divider()

# ── 下段：ログ ────────────────────────────────────────
st.subheader("📜 動作ログ")

if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        logs = json.load(f)
    if logs:
        import pandas as pd
        df = pd.DataFrame(logs[::-1])  # 新しい順
        df.columns = ["時刻", "患者ID", "リクエスト", "キット", "結果"]
        st.dataframe(df, use_container_width=True)
    else:
        st.caption("まだログがありません")
else:
    st.caption("まだログがありません")

# ── 自動更新 ──────────────────────────────────────────
st.caption("---")
auto_refresh = st.checkbox("⏱ 3秒ごとに自動更新", value=False)
if auto_refresh:
    import time
    time.sleep(3)
    st.rerun()
