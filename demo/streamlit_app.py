import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import streamlit as st  # noqa: E402

from ui.common.backend_bootstrap import start_backend  # noqa: E402

st.set_page_config(page_title="PreCareBot デモ", page_icon="🤖", layout="centered")

with st.spinner("バックエンドを起動しています（数秒）..."):
    backend_ok = start_backend()

st.markdown("# PreCareBot — ライブデモ")

if not backend_ok:
    st.error(
        "バックエンドの起動確認がタイムアウトしました。左のサイドバーから各ページを"
        "開き直すと復旧することがあります。"
    )

st.markdown(
    """
このデモは、看護現場の転倒予防を目的としたソフトウェアMVP「PreCareBot」を、
実際にブラウザから操作できる形で公開しています。詳しい設計・全機能は
[GitHubリポジトリ](https://github.com/SayokoAkiike/nursing-robot)を参照してください。

**左のサイドバーから3つのページを行き来できます。**

1. **患者用タブレット** — 患者役として、ボタン一つで看護師にリクエストを送る
2. **看護師ダッシュボード** — 看護師役として、届いたリクエストを確認・キット開放する
3. **巡回・要望分類デモ** — ロボットが患者に声掛けしたと仮定して、自由入力した発言が
   どう分類され、必要なら看護師エスカレーションが上がる様子を見る

**1と2を別々のブラウザタブで開いて**、患者側でボタンを押すと看護師側にリアルタイムで
届く様子を見るのが一番わかりやすいです。
"""
)

st.info(
    "このデモは公開・共有される sandbox です。実在の患者データは一切使用していません。"
    "音声認識・姿勢推定・埋め込み/LLMによる要望分類の高度な段階は、公開デモではメモリ節約の"
    "ため無効化しており、キーワードマッチのみで動作します（該当機能はローカル環境で確認できます、"
    "詳細は [docs/FEATURES.md](https://github.com/SayokoAkiike/nursing-robot/blob/main/docs/FEATURES.md)）。",
    icon="ℹ️",
)
