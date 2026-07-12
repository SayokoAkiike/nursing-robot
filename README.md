# PreCareBot

[![pytest](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](#license)
[![Live Demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nursing-robot-oyrvp7rqmyr5zjxclibdft.streamlit.app)

**看護現場の転倒予防を目的とした、安全制約つきベッドサイド見守りロボットのソフトウェアMVP。**
> 物理ロボットは実装していない、ソフトウェアのみのプロトタイプです。医療機器ではありません。

ナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がって転倒するリスクがある。特に自分から助けを求めにくい患者（高齢・認知機能低下・遠慮しがち）ほどこのリスクが高い。

PreCareBotは2つの方向からこれに対応する:

1. **配送ワークフロー** — 看護師が来る前にロボットがキットを届け、「立ち上がらずお待ちください」と表示する。キットは看護師の確認まで開放しない。
2. **巡回・見守りワークフロー** — ロボットが病棟を巡回して声掛けし、困りごとを能動的に拾って看護師へ通知する。会話が曖昧なら、キーワード → 埋め込み類似度 → ローカルLLM の順で段階的に踏み込んで分類する。位置情報だけでなく速度・加速度も見て、転倒の瞬間を静止画一枚では見逃さないようにしている。

いずれも音声・映像は外部に送信せず、モデル推論はすべてローカル（オフライン）で完結する。

```mermaid
flowchart LR
    UI["Streamlit UI\n(患者/看護師)"] -->|HTTP| API["FastAPI"]
    Robot["巡回・配送\nシミュレーション"] -->|HTTP| API
    API --> WF["workflow_service\nrounding_service"]
    WF --> Classify["要望分類\nキーワード→埋め込み→LLM"]
    WF --> Vision["姿勢推定\n離床・転倒検知"]
    WF --> DB[("SQLite / PostgreSQL")]
    WF --> Escalation["看護師エスカレーション"]
    DB --> Grafana["Analytics API / Grafana"]
```

より詳しい構成図・データモデルは [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) を参照。

---

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v
```

`DATABASE_URL`を`.env`で指定しない場合、`data/precare.db`のSQLiteファイルにフォールバックする（追加セットアップ不要）。API起動後は `http://localhost:8000/docs` でSwagger UI（全エンドポイントを実際に叩けるインタラクティブなリファレンス）が使える。

**手元でセットアップせずブラウザだけで触ってみたい場合**は、[ライブデモ](https://nursing-robot-oyrvp7rqmyr5zjxclibdft.streamlit.app)をどうぞ（キーワード分類のみ、ローカルのようなML拡張は無効化した公開sandbox版）。自分のStreamlit Community Cloudアカウントに同じ構成をデプロイする手順は [docs/DEMO.md](docs/DEMO.md) を参照（無料、GitHubアカウントのみで数分）。

<details>
<summary>初めて動かす場合のチェックリスト（クリックで展開）</summary>

- **ディスク容量**: ML機能（音声認識・姿勢推定・埋め込み分類・ローカルLLM）を全部試すなら3〜4GB程度の空き容量を見ておく
- **`llama-cpp-python`のビルド時間**: PyPIにプリビルドwheelが無く、`pip install`のたびにC++バックエンドをソースからビルドする。数分（環境によっては10分超）かかるが、フリーズしているわけではない
- **姿勢推定を使うなら**: `libGLESv2.so.2` / `libEGL.so.1`が追加で必要（`sudo apt-get install -y libgles2 libegl1`）
- **`HF_TOKEN`の設定を推奨**: ML機能はすべてHugging Faceから初回ダウンロードする。未認証アクセスはレート制限が低く、`429 Too Many Requests`にぶつかりやすい。[https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) でRead権限のトークンを発行し、`.env`の`HF_TOKEN=`に設定する

</details>

<details>
<summary>Docker実行（PostgreSQL + API + Grafana）</summary>

```bash
docker-compose up --build
```

`db`（postgres:16-alpine）・`backend`・`grafana`の3サービスが起動する。バックエンドは`http://localhost:8000`、Grafanaは`http://localhost:3000`（admin/admin、匿名Viewerアクセスも可）。UIはcomposeに含まれないため、必要ならローカルで別途起動する（`DATABASE_URL`を`.env`で`postgresql+psycopg2://precare:precare@localhost:5432/precare`に向ければ同じDBを共有できる）。

```bash
docker-compose down
```

</details>

<details>
<summary>品質チェック・デモデータ</summary>

```bash
# 品質チェック
ruff check .
mypy backend perception vision
pytest tests/ --cov=backend --cov=perception --cov=vision --cov-report=term-missing

# デモデータ（開発・デモ用、明示実行のみ、本番では使わない）
python -m backend.scripts.seed_demo_data --days 7 --tasks 20
python -m backend.scripts.reset_demo_data
```

</details>

---

## 実装済み機能

| カテゴリ | 内容 |
|---|---|
| 配送ワークフロー | リクエスト受信 → キット配送 → QR照合 → 看護師確認。ステートマシン・REST API・PostgreSQL永続化 |
| 巡回・見守りワークフロー | ロボットが巡回して声掛け → 要望分類 → 看護師エスカレーション。既存の配送フローとも接続 |
| 要望分類 | キーワード → 文埋め込み（sentence-transformers） → ローカルLLM（LFM2.5-1.2B-JP）の3段フォールバック |
| 音声認識 | faster-whisper、CPU・オフライン完結、VADによる無音除去 |
| 姿勢推定・離床検知 | MediaPipe Pose、静止位置＋速度/加速度の時系列判定 |
| 異常検知 | 患者ごとのエスカレーションパターンをscikit-learn IsolationForestで教師なし検知 |
| シミュレーション | ヘッドレスPyBulletでの配送・巡回フロー一括駆動、QR合成、ローカルGUIデモ |
| 監視 | Analytics API、Grafanaダッシュボード5枚 |
| 品質管理 | ruff / mypy / pytest（400件超）/ CI |

各機能の詳しい使い方・設計判断は [docs/FEATURES.md](docs/FEATURES.md) を参照。

<details>
<summary>ファイル単位の対応表（クリックで展開）</summary>

| 機能 | ファイル |
|------|---------|
| 患者リクエストUI | `ui/patient_request_app/app.py` |
| 看護師ダッシュボード | `ui/nurse_dashboard/app.py` |
| REST API (FastAPI) | `backend/main.py` |
| ワークフロー・ステートマシン | `robot_control/state_machine.py`, `backend/services/robot_service.py` |
| リクエスト作成・照合・状態遷移 | `backend/services/workflow_service.py` |
| QRコード生成・照合 | `vision/qr_detection/`, `perception/` |
| DB永続化・マイグレーション | `backend/db/`, `alembic/` |
| Analytics API | `backend/api/routes_analytics.py`, `backend/services/analytics_service.py` |
| Docker化 | `Dockerfile`, `docker-compose.yml` |
| ヘッドレスPyBulletシミュレーション | `perception/pybullet_source.py`, `backend/scripts/run_simulated_delivery.py` |
| Grafana | `grafana/provisioning/` |
| 巡回ドメインモデル・状態遷移・エスカレーション | `backend/db/models.py`, `backend/services/rounding_service.py`, `backend/services/escalation_service.py` |
| 巡回・エスカレーションAPI | `backend/api/routes_rounding.py`, `backend/api/routes_escalations.py` |
| 巡回シミュレーション | `backend/scripts/run_simulated_rounding.py` |
| ドメイン登録（Hospital/Ward/Room/Bed/Patient/Nurse/Robot） | `backend/services/domain_service.py`, `backend/api/routes_domain.py` |
| マルチロボット対応 | `backend/services/workflow_service.py`, `backend/services/rounding_service.py` |
| UIリアルタイム更新 | `ui/patient_request_app/app.py`, `ui/nurse_dashboard/app.py` |
| 実音声認識 | `perception/speech_source.py`, `perception/speech_recognizer.py` |
| 実姿勢推定・離床検知 | `perception/pose_detector.py`, `backend/services/bed_exit_service.py` |
| 埋め込みベース要望分類 | `backend/services/semantic_classification_service.py` |
| ローカルLLM要望分類 | `backend/services/llm_classification_service.py` |
| エスカレーション異常検知 | `backend/services/escalation_anomaly_service.py` |

</details>

---

## API

主要なエンドポイントのみ抜粋。全エンドポイントは起動後 `http://localhost:8000/docs`（Swagger UI）で確認・実行できる。

| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| POST | `/requests` | - | 患者リクエスト作成 |
| POST | `/tasks/{id}/verify` | 🔒 nurse | QR照合 |
| POST | `/rounding/start` | - | 巡回セッション開始 |
| POST | `/rounding/{id}/classify-need` | - | 患者応答の登録・要望分類 |
| GET | `/escalations` | - | エスカレーション一覧 |
| POST | `/escalations/{id}/ack` | 🔒 nurse | 看護師確認 |
| POST | `/escalations/vision-report` | 🔒 robot | 映像検知による直接エスカレーション |
| GET | `/analytics/*` | - | 各種集計・異常検知（[一覧](docs/FEATURES.md#analytics-api)） |

<details>
<summary>全エンドポイント一覧</summary>

| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| GET | `/state?robot_id=` | - | 現在の状態（`robot_id`省略時はデフォルトロボット） |
| GET | `/requests` | - | リクエスト一覧 |
| GET | `/requests/{id}` | - | リクエスト詳細 |
| POST | `/requests/{id}/cancel` | - | 患者キャンセル |
| POST | `/tasks/{id}/transition` | 🔒 nurse | 状態遷移 |
| POST | `/tasks/{id}/emergency-stop` | 🔒 nurse | 緊急停止 |
| POST | `/tasks/{id}/reset` | 🔒 nurse | リセット |
| POST | `/tasks/{id}/cancel` | 🔒 nurse | 看護師キャンセル |
| GET | `/logs` | - | ログ |
| GET | `/analytics/summary` | - | 件数系の集計 |
| GET | `/analytics/verification-failures` | - | QR照合失敗の内訳 |
| GET | `/analytics/state-durations` | - | 状態別の平均滞在時間 |
| GET | `/rounding/{id}` | - | 巡回セッション詳細 |
| POST | `/rounding/{id}/detect-patient` | - | 患者発見 |
| POST | `/rounding/{id}/start-interaction` | - | 声掛け開始 |
| POST | `/rounding/{id}/provide-information` | - | 情報提供のみで完了 |
| POST | `/rounding/{id}/escalate` | - | 看護師エスカレーション作成 |
| POST | `/rounding/{id}/require-delivery` | - | 配送フローへ接続 |
| GET | `/escalations/{id}` | - | エスカレーション詳細 |
| GET | `/analytics/rounding-summary` | - | 巡回ワークフローの件数系集計 |
| GET | `/analytics/escalation-breakdown` | - | priority/need/status別内訳 |
| GET | `/analytics/escalation-anomalies` | - | エスカレーションパターンの異常検知 |
| GET | `/patients`, `/patients/{id}` | - | 患者一覧・詳細 |
| GET | `/robots` | - | ロボット一覧（status付き） |
| GET | `/wards` | - | 病棟一覧（部屋→ベッド→入居患者） |

🔒 nurse = `x-nurse-token`ヘッダー必須、🔒 robot = `x-robot-token`ヘッダー必須

</details>

---

## 制約・ロードマップ

- 物理ロボットは未実装（PyBulletシーン内でも位置を直接設定しているのみ）
- ロボット1台につき同時アクティブタスクは1件まで。マルチロボット対応はサービス層まで済んでいるが、患者→ロボットの自動割り当てと複数病棟対応は未接続
- UIの自動更新はポーリング（2秒間隔）で、真のプッシュ通知ではない
- Dockerイメージはローカル/デモ用（本番デプロイには別途secrets管理等が必要）

<details>
<summary>フェーズごとの進捗</summary>

| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1–2 | API設計・UI分離・ステートマシン | 完了 |
| Phase 3 | PostgreSQL化・タスクリソースモデル・Perception・CI/品質整備 | 完了 |
| Phase 3.5 | 状態遷移履歴・Analytics API・デモデータ・Docker化 | 完了 |
| Phase 4 | ヘッドレスPyBulletシミュレーション・Grafana・ローカルGUIデモ | 完了 |
| Phase 4.5 | 巡回ワークフロー・実音声認識・実姿勢推定・ドメイン登録・マルチロボット・UIリアルタイム化 | 完了 |
| Phase 4.5後半 | 要望分類の埋め込み/LLMフォールバック・離床検知の時系列化・異常検知 | 完了 |
| Phase 5 | 実機MVP・自動ロボット割り当て・複数病棟対応 | 未着手 |

</details>

---

## License

MIT License
