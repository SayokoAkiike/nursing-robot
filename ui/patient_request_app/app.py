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

state = load_state()
robot_state = state.get("robot_state", "IDLE")

st.markdown("## 🏥 203号室　患者 A")

if robot_state not in ["IDLE", "COMPLETED", "ERROR"]:
    st.warning("⚠️ 立ち上がらずお待ちください / Please do not stand up.")
    req = state.get("request", "")
    st.info(f"📋 リクエスト中：{req}　｜　🤖 {robot_state}")
    if robot_state == "REQUEST_RECEIVED":
        if st.button("✖️ リクエストを取り消す", use_container_width=True):
            save_state({"request": None, "robot_state": "IDLE"})
            st.rerun()
    else:
        st.caption("※ ロボットが移動中のため取り消しは看護師にお声がけください")
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
        if st.button("🚽 トイレに行きたい", use_container_width=True, key="toilet"):
            save_state({"request": "トイレ介助", "kit": "KIT_TOILETING_A",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "転倒リスクあり",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            st.rerun()
    with col2:
        if st.button("💧 水がほしい", use_container_width=True, key="water"):
            save_state({"request": "水の提供", "kit": "KIT_WATER",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "なし",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            st.rerun()
    with col3:
        if st.button("💉 点滴が気になる", use_container_width=True, key="iv"):
            save_state({"request": "点滴確認", "kit": "KIT_IV_ALERT",
                "patient_id": "PATIENT_A_ROOM_203", "risk": "要確認",
                "robot_state": "REQUEST_RECEIVED", "timestamp": datetime.now().isoformat()})
            st.rerun()
    st.divider()
    st.caption("🔔 ボタンを押すと看護師に通知され、ロボットが準備を開始します")
