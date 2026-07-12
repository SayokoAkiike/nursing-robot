import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
import streamlit as st  # noqa: E402

from ui.common.backend_bootstrap import DEMO_BACKEND_URL, start_backend  # noqa: E402
from ui.common.demo_seed import seed_anomaly_demo_data  # noqa: E402
from ui.common.style import CSS  # noqa: E402

start_backend()

st.set_page_config(page_title="Analytics・異常検知デモ", page_icon="📊", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

st.markdown("## Analytics・異常検知デモ")
st.caption(
    "配送・巡回ワークフローの集計API（`/analytics/*`）と、患者ごとのエスカレーションパターンの"
    "教師なし異常検知（`GET /analytics/escalation-anomalies`）をそのまま表示している。"
)

st.info(
    "起動直後はデータがほとんど無い状態。特に異常検知は5人以上の患者データが無いと"
    "「データ不足」として空の結果を返す設計（無理に数値を出さない、詳細は"
    "[docs/FEATURES.md](https://github.com/SayokoAkiike/nursing-robot/blob/main/docs/FEATURES.md#エスカレーションパターンの異常検知)）"
    "なので、下のボタンで合成データを投入すると分かりやすい。",
    icon="ℹ️",
)

if st.button("デモ用の合成データを投入する（患者7名分の巡回・エスカレーション履歴）", type="primary"):
    with st.spinner("合成データを投入中..."):
        result = seed_anomaly_demo_data()
    st.success(
        f"{len(result['created_patients'])}名分の巡回セッションを投入しました。"
        f"うち **{result['outlier_patient_id']}** は意図的に異常パターン（URGENT多発）にしています。"
    )
    st.rerun()

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 配送ワークフロー集計")
    try:
        summary = requests.get(f"{DEMO_BACKEND_URL}/analytics/summary", timeout=5).json()
        st.metric("総リクエスト数", summary.get("total_requests", 0))
        m1, m2 = st.columns(2)
        m1.metric("完了", summary.get("completed_requests", 0))
        m2.metric("キャンセル", summary.get("cancelled_requests", 0))
    except Exception as e:
        st.error(f"取得エラー: {e}")

with col2:
    st.markdown("#### 巡回ワークフロー集計")
    try:
        rounding_summary = requests.get(f"{DEMO_BACKEND_URL}/analytics/rounding-summary", timeout=5).json()
        st.metric("巡回セッション数", rounding_summary.get("total_rounding_sessions", 0))
        m1, m2 = st.columns(2)
        m1.metric("エスカレーション数", rounding_summary.get("escalations_created", 0))
        m2.metric("うちURGENT", rounding_summary.get("urgent_escalations", 0))
    except Exception as e:
        st.error(f"取得エラー: {e}")

st.divider()
st.markdown("#### エスカレーションのpriority/need別内訳")
try:
    breakdown = requests.get(f"{DEMO_BACKEND_URL}/analytics/escalation-breakdown", timeout=5).json()
    b1, b2 = st.columns(2)
    with b1:
        by_priority = breakdown.get("by_priority", [])
        if by_priority:
            df = pd.DataFrame(by_priority).set_index("priority")
            st.bar_chart(df)
        else:
            st.caption("データがありません。")
    with b2:
        by_need = breakdown.get("by_detected_need", [])
        if by_need:
            df = pd.DataFrame(by_need).set_index("detected_need")
            st.bar_chart(df)
        else:
            st.caption("データがありません。")
except Exception as e:
    st.error(f"取得エラー: {e}")

st.divider()
st.markdown("#### エスカレーションパターンの異常検知（教師なし学習）")
try:
    anomalies = requests.get(f"{DEMO_BACKEND_URL}/analytics/escalation-anomalies", timeout=5).json()
    total = anomalies.get("total_patients_analyzed", 0)
    min_required = anomalies.get("min_patients_required", 5)

    if total < min_required:
        st.warning(
            f"分析対象の患者数が{total}人で、比較に必要な{min_required}人未満のため、"
            "異常検知は実行されません（上のボタンでデータを投入すると閾値を超えます）。"
        )
    else:
        anomalous = anomalies.get("anomalous_patients", [])
        st.write(f"分析対象: {total}人の患者")
        if anomalous:
            st.error(f"{len(anomalous)}人の患者で、統計的に外れたエスカレーションパターンを検知しました。")
            # See ui/nurse_dashboard/app.py's render_log() for why
            # fillna("") is here -- avg_time_to_ack_seconds is None for
            # any patient with no acknowledged escalations yet, which
            # could make that whole column all-null and hit the same
            # pyarrow crash observed in CI for that other table.
            st.dataframe(pd.DataFrame(anomalous).fillna(""), use_container_width=True)
        else:
            st.success("統計的な外れ値は検知されませんでした。")
except Exception as e:
    st.error(f"取得エラー: {e}")
