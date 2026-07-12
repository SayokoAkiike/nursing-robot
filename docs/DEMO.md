# 公開デモ（Streamlit Community Cloud）

`demo/streamlit_app.py` + `demo/pages/` は、このリポジトリを**1つのStreamlit Community Cloudデプロイ**として公開するための構成。患者用タブレット・看護師ダッシュボード・巡回要望分類デモの3ページが、同一プロセス内でバックグラウンドスレッドとして起動する本物のFastAPIバックエンドを共有する。

`demo/`という専用サブディレクトリに分けているのには理由がある。**Streamlit Community Cloudには依存関係ファイルを選ぶ設定が存在せず**、常に固定ファイル名`requirements.txt`を自動検出する（公式ドキュメント: [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)）。探索順は「エントリーポイントと同じディレクトリ → リポジトリルート」で、同じディレクトリのものが優先される。そのため、エントリーポイント（`demo/streamlit_app.py`）と専用の`demo/requirements.txt`を同じディレクトリに置くことで、リポジトリルートの（`torch`/`mediapipe`/`llama-cpp-python`を含む）本来の`requirements.txt`より優先させている。

## デプロイ手順（あなたのブラウザ操作が必要）

Streamlit Community Cloudへの実際のデプロイは、GitHubアカウントとの連携が必要なため、ブラウザから手動で行う必要がある。

1. [share.streamlit.io](https://share.streamlit.io) にアクセスし、GitHubアカウントでログイン
2. 「Create app」→「Deploy a public app from GitHub」
3. Repository: `SayokoAkiike/nursing-robot`、Branch: `main`（このPRのマージ後）
4. **Main file path**: `demo/streamlit_app.py`（`streamlit_app.py`ではない点に注意）
5. 「Advanced settings」を開き、**Python version 3.11**を選択（依存関係ファイルを選ぶ設定は無い——上記の通り`demo/requirements.txt`が自動的に優先される）
6. 「Deploy」をクリック。初回ビルドは数分かかる

デプロイ後に発行されるURL（`https://xxxxx.streamlit.app`のような形式）を、[README.md](../README.md)の該当バッジに設定する。

**既に`Main file path`を`streamlit_app.py`（サブディレクトリ無し）でデプロイしてしまっている場合**：一度アプリを削除して、`demo/streamlit_app.py`を指定して再デプロイする必要がある（Streamlit CloudはMain file pathを後から変更できないため）。

## このデモでできること・できないこと

| 機能 | 公開デモ | ローカル/Codespaces |
|---|---|---|
| 患者用タブレット・看護師ダッシュボード | ✅ フル機能 | ✅ |
| 巡回・キーワード要望分類・エスカレーション | ✅ フル機能 | ✅ |
| 埋め込み類似度・ローカルLLMによる分類フォールバック | ❌（`demo/requirements.txt`に依存を含めていない） | ✅ |
| 実音声認識・実姿勢推定 | ❌（同上、加えてWebカメラ/マイクは公開環境に無い） | ✅（ローカル限定） |
| エスカレーション異常検知 | 理論上は動く（`scikit-learn`は軽量）が、5人以上のデータが要るため公開デモの少量データでは空の結果になりやすい | ✅ |

キーワードに一致しない発話を入力すると、`rounding_service._classify_with_ml_fallbacks()`は埋め込み/LLM段階への到達を試みるが、それらのパッケージが未インストールのため`ImportError`となり、既存の安全設計（try/exceptで前段階の結果へフォールバック）によって自動的に`unknown`に倒れる。**新しいフィーチャーフラグや条件分岐を追加する必要はなかった**——このプロジェクトが最初からPR31以降ずっと守ってきた「MLフォールバックが使えなくても壊れない」という設計方針が、そのままこの用途に転用できた。

## なぜこの構成か

- **1プロセス・1エントリポイント**: Streamlit Community Cloudは1デプロイにつき1つのメインスクリプトしかホストできない。患者用・看護師用の2つのStreamlitアプリを別々にデプロイすると、互いに独立したデータベースを持つことになり、「患者がリクエストしたら看護師側にリアルタイムで届く」というこのプロダクトの核心的な体験を再現できない。`st.cache_resource`でバックエンドをプロセス内に1回だけ起動し、両ページから同じHTTP API（`ui/common/api_client.py`、既存コード無改修）越しに触ることで、この制約下でも本物の共有状態を実現している
- **既存UIコードの再利用**: `ui/patient_request_app/app.py` / `ui/nurse_dashboard/app.py`は`main()`関数でラップしただけで、ロジックは1行も変えていない。`streamlit run ui/patient_request_app/app.py`によるローカル単体起動も引き続き動作する
- **`demo/`サブディレクトリ + `demo/requirements.txt`**: 上記の通り、Streamlit Cloudの「エントリーポイントと同じディレクトリのrequirements.txtが優先される」という探索順を利用して、デモ専用の最小依存構成をリポジトリルートの開発用`requirements.txt`と衝突させずに共存させている
- **最小構成の`demo/requirements.txt`**: `backend/`内のどのモジュールも、重いMLライブラリ（torch・mediapipe・llama-cpp-python）をモジュールのトップレベルではimportしていない（すべて関数内での遅延import）。この設計のおかげで、それらのパッケージを最初からインストールしないだけで、要望分類は自動的にキーワード段階のみで安全に動作する

