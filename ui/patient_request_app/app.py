"""
患者リクエストUI (Day 5)
実行方法: streamlit run ui/patient_request_app/app.py
"""

import streamlit as st
import json
import os
from datetime import datetime

# ── ページ設定 ───────────────────────────────────────
st.set_page_config(
    page_title="患者リクエスト",
    page_icon="🏥",
    layout="centered",
)

# ── 共有状態ファイルのパス ───────────────────────────
STATE_FILE = "shared_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE", "timestamp": None}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ── スタイル ─────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #f0f8ff; }
    .patient-header {
        text-align: center;
        padding: 20px;
        background: #1a73e8;
        color: white;
        border-radius: 12px;
        margin-bottom: 24px;
    }
    .status-box {
        padding: 16px;
        border-radius: 10px;
        margin-top: 20px;
        font-size: 18px;
        text-align: center;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 2px solid #ffc107;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ── ヘッダー ─────────────────────────────────────────
st.markdown("""
<div class="patient-header">
    <h2>🏥 203号室 患者A</h2>
    <p>ご用件をボタンで教えてください</p>
</div>
""", unsafe_allow_html=True)

# ── 現在の状態を読み込む ─────────────────────────────
state = load_state()
robot_state = state.get("robot_state", "IDLE")
current_request = state.get("request")

# ── リクエスト済みの場合は待機画面 ──────────────────
if robot_state not in ["IDLE", "COMPLETED", "ERROR"]:
    st.markdown("""
    <div class="warning-box">
        ⚠️ 立ち上がらずお待ちください<br>
        <span style="font-size:16px">看護師がまもなく参ります</span><br><br>
        Please do not stand up.<br>
        <span style="font-size:14px">A nurse will arrive shortly.</span>
    </div>
    """, unsafe_allow_html=True)

    st.info(f"🤖 ロボット状態：{robot_state}")

    if current_request:
        st.success(f"📋 リクエスト：{current_request}")

    # 自動更新
    st.caption("ページは自動更新されます...")
    st.button("🔄 更新")

# ── リクエストボタン ─────────────────────────────────
else:
    if robot_state == "COMPLETED":
        st.success("✅ 介助が完了しました。ありがとうございました。")

    st.markdown("### ご用件を選んでください")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🚽\nトイレに\n行きたい", use_container_width=True, key="toilet"):
            new_state = {
                "request": "トイレ介助",
                "request_en": "Toileting assistance",
                "kit": "KIT_TOILETING_A",
                "patient_id": "PATIENT_A_ROOM_203",
                "risk": "転倒リスクあり",
                "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            }
            save_state(new_state)
            st.rerun()

    with col2:
        if st.button("💧\n水が\nほしい", use_container_width=True, key="water"):
            new_state = {
                "request": "水の提供",
                "request_en": "Water request",
                "kit": "KIT_WATER",
                "patient_id": "PATIENT_A_ROOM_203",
                "risk": "なし",
                "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            }
            save_state(new_state)
            st.rerun()

    with col3:
        if st.button("💉\n点滴が\n気になる", use_container_width=True, key="iv"):
            new_state = {
                "request": "点滴確認",
                "request_en": "IV check",
                "kit": "KIT_IV_ALERT",
                "patient_id": "PATIENT_A_ROOM_203",
                "risk": "要確認",
                "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            }
            save_state(new_state)
            st.rerun()

    st.markdown("---")
    st.caption("🔔 ボタンを押すと看護師に通知され、ロボットが準備を開始します")
