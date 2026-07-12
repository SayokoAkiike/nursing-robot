import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import requests  # noqa: E402
import streamlit as st  # noqa: E402

from robot_control.config import PATIENTS  # noqa: E402
from ui.common.backend_bootstrap import DEMO_BACKEND_URL, start_backend  # noqa: E402
from ui.common.style import CSS  # noqa: E402

start_backend()

st.set_page_config(page_title="巡回・要望分類デモ", page_icon="🚶", layout="centered")
st.markdown(CSS, unsafe_allow_html=True)

NURSE_TOKEN = "precare-dev-token-2026"
EXAMPLE_PHRASES = [
    "トイレに行きたいです",
    "喉が渇きました",
    "少し不安で眠れないんです",
    "胸が痛いです、苦しいです",
    "大丈夫です、特にないです",
]

st.markdown("## 巡回・要望分類デモ")
st.caption(
    "ロボットが病棟を巡回して患者に声掛けした、という想定です。"
    "自由に発言を入力すると、実際のキーワード分類ロジックがその場で判定します。"
)
st.info(
    "このデモは軽量なキーワードマッチのみを実行します。埋め込み類似度・ローカルLLMへの"
    "フォールバックは、公開デモではメモリ節約のため無効化しています"
    "（ローカル環境では自動的に有効になります、詳細はリポジトリの docs/FEATURES.md）。",
    icon="ℹ️",
)

patient_id = st.selectbox("患者", options=list(PATIENTS.keys()), format_func=lambda pid: f"{pid}（{PATIENTS[pid].get('room', '?')}号室）")
room = PATIENTS.get(patient_id, {}).get("room", "203")

response_text = st.text_input("患者の発言を入力してください", placeholder="例: トイレに行きたいです")

st.caption("例文をクリックして試すこともできます:")
example_cols = st.columns(len(EXAMPLE_PHRASES))
for col, phrase in zip(example_cols, EXAMPLE_PHRASES):
    with col:
        if st.button(phrase, use_container_width=True, key=f"ex_{phrase}"):
            st.session_state["_demo_response_text"] = phrase
            st.rerun()

if "_demo_response_text" in st.session_state:
    response_text = st.session_state.pop("_demo_response_text")

run_clicked = st.button("巡回を実行して分類する", type="primary", use_container_width=True, disabled=not response_text)

if run_clicked and response_text:
    nurse_headers = {"x-nurse-token": NURSE_TOKEN}
    try:
        with st.status("巡回を実行中...", expanded=True) as status:
            st.write(f"ロボットが{room}号室を巡回開始")
            started = requests.post(f"{DEMO_BACKEND_URL}/rounding/start", json={"room": room}, timeout=5).json()
            session_id = started["rounding_session_id"]

            st.write(f"患者を発見: {patient_id}")
            requests.post(
                f"{DEMO_BACKEND_URL}/rounding/{session_id}/detect-patient",
                json={"patient_id": patient_id},
                timeout=5,
            )

            interaction = requests.post(
                f"{DEMO_BACKEND_URL}/rounding/{session_id}/start-interaction", timeout=5
            ).json()
            st.write(f"声掛け: 「{interaction['prompt']}」")
            st.write(f"患者の応答: 「{response_text}」")

            classification = requests.post(
                f"{DEMO_BACKEND_URL}/rounding/{session_id}/classify-need",
                json={"patient_response": response_text, "input_mode": "simulated"},
                timeout=5,
            ).json()
            st.write(
                f"分類結果: **{classification['detected_need']}** "
                f"（優先度: {classification['escalation_level']}、ルート: {classification['route']}）"
            )

            route = classification["route"]
            if route == "INFORMATION_ONLY":
                requests.post(f"{DEMO_BACKEND_URL}/rounding/{session_id}/provide-information", timeout=5)
                st.write("看護師エスカレーションは不要と判断されました。セッション完了。")
            elif route in ("NURSE_NOTIFICATION", "URGENT_ESCALATION"):
                requests.post(
                    f"{DEMO_BACKEND_URL}/rounding/{session_id}/escalate",
                    json={
                        "summary": classification["summary"],
                        "priority": classification["escalation_level"],
                        "suggested_action": classification["suggested_action"],
                        "reason": classification["detected_need"],
                        "route": route,
                    },
                    headers=nurse_headers,
                    timeout=5,
                )
                st.write("看護師エスカレーションを作成しました。")
            elif route == "DELIVERY_REQUIRED":
                requests.post(
                    f"{DEMO_BACKEND_URL}/rounding/{session_id}/require-delivery",
                    json={"request_type": classification["detected_need"], "patient_id": patient_id},
                    timeout=5,
                )
                st.write("配送ワークフローへ接続しました（患者用タブレットページで確認できます）。")

            status.update(label="完了", state="complete")

        if classification["route"] in ("NURSE_NOTIFICATION", "URGENT_ESCALATION"):
            st.success(
                "エスカレーションが作成されました。**看護師ダッシュボードページ**を開くと、"
                "このエスカレーションが実際に表示されているのを確認できます。"
            )
    except Exception as e:
        st.error(f"エラー: {e}")
