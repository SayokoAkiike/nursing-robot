"""
患者リクエストUI
実行方法: python -m streamlit run ui/patient_request_app/app.py --server.port 8501
"""

import streamlit as st
import json, os, time
from datetime import datetime

st.set_page_config(page_title="患者リクエスト", page_icon="🏥", layout="centered")

STATE_FILE = "shared_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"request": None, "robot_state": "IDLE"}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

st.markdown("""
<style>
div.stButton > button {
    height: 90px;
    font-size: 18px;
    border-radius: 16px;
    border: 2px solid #ddd;
    background: white;
}
div.stButton > button:hover { border-color: #1a73e8; color: #1a73e8; }
.cancel-btn > button {
    background: #fff5f5 !important;
    border-color: #f87171 !important;
    color: #dc2626 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; padding:20px; background:linear-gradient(135deg,#1a73e8,#0d47a1);
color:white; border-radius:16px; margin-bottom:24px;">
<h2 style="margin:0">🏥 203号室　患者 A</h2>
<p style="margin:8px 0 0; opacity:0.9">ご用件をボタンで教えてください</p>
</div>
""", unsafe_allow_html=True)

state = load_state()
robot_state = state.get("robot_state", "IDLE")

if robot_state not in ["IDLE", "COMPLETED", "ERROR"]:
    st.markdown("""
    <div style="background:#fff8e1; border:2px solid #f59e0b; border-radius:16px;
    padding:28px; text-align:center; margin-bottom:20px;">
        <div style="font-size:40px">⚠️</div>
        <div style="font-size:22px; font-weight:bold; color:#92400e; margin:8px 0">
            立ち上がらずお待ちください
        </div>
        <div style="font-size:14px; color:#78350f">看護師がまもなく参ります</div>
        <hr style="border-color:#f59e0b; margin:16px 0">
        <div style="font-size:16px; color:#92400e">Please do not stand up.</div>
        <div style="font-size:13px; color:#78350f">A nurse will arrive shortly.</div>
    </div>
    """, unsafe_allow_html=True)

    req = state.get("request", "")
    st.info(f"📋 リクエスト中：**{req}**　｜　🤖 ロボット状態：`{robot_state}`")

    if robot_state == "REQUEST_RECEIVED":
        st.markdown('<div class="cancel-btn">', unsafe_allow_html=True)
        if st.button("✖️ リクエストを取り消す", use_container_width=True):
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("※ ロボットが移動中のため取り消しは看護師にお声がけください")

    if st.button("🔄 画面を更新する", use_container_width=True):
        st.rerun()

    # 3秒ごとに自動更新
    time.sleep(3)
    st.rerun()

elif robot_state == "COMPLETED":
    st.success("✅ 介助が完了しました。ありがとうございました。")
    if st.button("🔄 最初の画面に戻る", use_container_width=True):
        save_state({"request": None, "robot_state": "IDLE"})
        st.rerun()

elif robot_state == "ERROR":
    st.error("🚨 エラーが発生しました。看護師をお呼びください。")
    if st.button("🔄 リセット", use_container_width=True):
        save_state({"request": None, "robot_state": "IDLE"})
        st.rerun()

else:
    st.markdown("### ご用件を選んでください")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🚽\nトイレに\n行きたい", use_container_width=True, key="toilet"):
            save_state({
                "request": "トイレ介助", "request_en": "Toileting assistance",
                "kit": "KIT_TOILETING_A", "patient_id": "PATIENT_A_ROOM_203",
                "risk": "転倒リスクあり", "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            })
            st.rerun()
    with col2:
        if st.button("💧\n水が\nほしい", use_container_width=True, key="water"):
            save_state({
                "request": "水の提供", "request_en": "Water request",
                "kit": "KIT_WATER", "patient_id": "PATIENT_A_ROOM_203",
                "risk": "なし", "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            })
            st.rerun()
    with col3:
        if st.button("💉\n点滴が\n気になる", use_container_width=True, key="iv"):
            save_state({
                "request": "点滴確認", "request_en": "IV check",
                "kit": "KIT_IV_ALERT", "patient_id": "PATIENT_A_ROOM_203",
                "risk": "要確認", "robot_state": "REQUEST_RECEIVED",
                "timestamp": datetime.now().isoformat(),
            })
            st.rerun()

    st.divider()
    st.caption("🔔 ボタンを押すと看護師に通知され、ロボットが準備を開始します")
