# PreCareBot — 看護現場の安全制約つきワークフロー（ソフトウェアMVP）

[![pytest](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml/badge.svg?branch=phase1-phase2)](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml)

> **Software-only prototype — not a medical device, not for production use.**

PreCareBot は、看護現場の転倒予防を目的とした「安全制約つきベッドサイドアシストロボット」の**ソフトウェアMVP**です。
物理ロボットは実装しておらず、患者リクエスト受信・キット配送・QR照合・看護師確認というワークフローを、ステートマシンとREST APIで設計・実装しています。

---

## 🎯 解決する問題

病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして転倒するリスクがある。

**設計アプローチ**: 看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。キットは看護師が確認・承認するまで開放しない（安全制約）。

---

## 📦 現在実装済み

| 機能 | ファイル | 状態 |
|------|---------|------|
| 患者リクエストUI | `ui/patient_request_app/app.py` | ✅ |
| 看護師ダッシュボード | `ui/nurse_dashboard/app.py` | ✅ |
| REST API (FastAPI) | `backend/main.py` | ✅ |
| ワークフロー・ステートマシン | `robot_control/state_machine.py` | ✅ |
| サービス層（ロボットタスクの実行・状態遷移） | `backend/services/robot_service.py` | ✅ |
| サービス層（リクエスト作成・キャンセル・照合・状態遷移履歴記録） | `backend/services/workflow_service.py` | ✅ |
| QRコード生成・照合 | `vision/qr_detection/` | ✅ |
| イベントログ（`workflow_service`内`_log()`が`robot_events`へ記録） | `backend/services/workflow_service.py` | ✅ |
| PostgreSQL/SQLAlchemy永続化 + Alembicマイグレーション | `backend/db/`, `alembic/` | ✅ |
| タスクリソースモデル（care_requests/robot_tasks/kit_verifications、ロボット単位の同時実行制約） | `backend/db/models.py`, `backend/services/workflow_service.py` | ✅ |
| 状態遷移履歴（全state変化を`task_state_transitions`に記録） | `backend/db/models.py`, `backend/services/workflow_service.py` | ✅ |
| QR照合の期待値/実測値分離（expected_*/scanned_*） | `backend/db/models.py`, `backend/services/workflow_service.py` | ✅ |
| Analytics API（件数集計・照合失敗内訳・状態滞在時間） | `backend/api/routes_analytics.py`, `backend/services/analytics_service.py` | ✅ |
| デモデータ生成・リセット（開発・デモ用） | `backend/scripts/seed_demo_data.py`, `backend/scripts/reset_demo_data.py` | ✅ |
| Perceptionモジュール（複数フレーム確定QR検出＋照合APIクライアント） | `perception/` | ✅ |
| 合成QRデモ動画生成（実写映像不使用） | `vision/qr_detection/demo/` | ✅ |
| QR検出の評価ベンチマーク（confirm_frames毎の検出成功率・所要フレーム数・不安定検出数） | `perception/evaluate_detector.py` | ✅ |
| バックエンドAPIのDocker化（`docker-compose up`でDB+APIを一括起動） | `Dockerfile`, `docker-compose.yml` | ✅ |
| 品質管理（ruff / mypy / pytest-cov / CI） | `ruff.toml`, `mypy.ini`, `.coveragerc`, `.github/workflows/pytest.yml` | ✅ |
| pytest テスト（133件） | `tests/` （API/workflow service/state machine/repositories/verification/perception/vision/analytics/Docker設定） | ✅ |

## ❌ 未実装（今後の予定）

| 機能 | 予定フェーズ |
|------|------------|
| PyBullet 病室シミュレーション | Phase 4 |
| 実カメラでのリアルタイムQRスキャン（現状は合成動画/画像ディレクトリ入力のみ検証済み） | Phase 4 |
| 物理ロボット制御・ナビゲーション | Phase 4 |
| マルチロボット・複数病棟対応 | Phase 5 |

---

## 🚀 Quick Start

### ローカル実行（venv、SQLiteフォールバック）

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v
```

`DATABASE_URL`を`.env`で指定しない場合、`data/precare.db`のSQLiteファイルにフォールバックする（`pytest`やちょっとした動作確認に十分、追加セットアップ不要）。

### Docker実行（PR13、PostgreSQL + バックエンドAPI）

```bash
docker-compose up --build
```

`db`（`postgres:16-alpine`）と`backend`（このリポジトリの`Dockerfile`からビルドしたFastAPI）の2サービスが、`backend`が`db`のヘルスチェック通過を待ってから順に起動する。バックエンドは `http://localhost:8000` で待ち受け（Swagger UIは `/docs`）。UI（Streamlit）はcomposeに含めていないので、必要ならローカルで別途起動する（上のQuick Start参照、`DATABASE_URL`を`.env`で`postgresql+psycopg2://precare:precare@localhost:5432/precare`に向ければ同じDBを共有できる）。

```bash
docker-compose down
```

で停止。`NURSE_TOKEN` / `ALLOWED_ORIGINS`は`docker-compose.yml`内で環境変数展開されており、ホスト側で環境変数`NURSE_TOKEN`を設定すればそちらが優先される（未設定時はdev用のデフォルト値）。

### 品質チェック（PR7）

```bash
ruff check .
mypy backend perception vision
pytest tests/ --cov=backend --cov=perception --cov=vision --cov-report=term-missing
```

### デモデータ（PR12、開発・デモ用 -- 本番では使わない）

Analytics API（`/analytics/*`）の中身を実データで確認するためのスクリプト。明示的にコマンドを実行したときだけ動作し、起動時に自動実行されることはない。ロボットにアクティブなタスクがある状態では拒否される（実行中タスクを壊さない）。

```bash
# 直近7日間に散らばる20件の合成リクエストを生成（正常完了/患者・看護師キャンセル/QR照合NG/緊急停止/看護師確認待ちが長いケースを含む）
python -m backend.scripts.seed_demo_data --days 7 --tasks 20

# 生成したデータを全て削除（確認プロンプトあり。--yesでスキップ可）
python -m backend.scripts.reset_demo_data
```

---

## 🗂️ データモデル

`backend/db/models.py`で定義される5テーブル。列の型はSQLite/PostgreSQL両対応のため汎用（String/Integer/Text）にしている。以下は論理的な関連を示すもので、SQLAlchemyレベルの`ForeignKey`制約は現状未設定（アプリケーション側で整合性を保証している）。

```mermaid
erDiagram
    CARE_REQUESTS ||--o{ ROBOT_TASKS : "request_id"
    ROBOT_TASKS ||--o{ KIT_VERIFICATIONS : "task_id"
    ROBOT_TASKS ||--o{ TASK_STATE_TRANSITIONS : "task_id"
    CARE_REQUESTS ||--o{ ROBOT_EVENTS : "request_id"
    ROBOT_TASKS ||--o{ ROBOT_EVENTS : "task_id"

    CARE_REQUESTS {
        string id PK
        string patient_id
        string request_type
        string priority
        string status
        string created_at
        string completed_at
    }
    ROBOT_TASKS {
        string id PK
        string request_id
        string robot_id
        string state
        string kit_id
        string assigned_at
        string updated_at
    }
    KIT_VERIFICATIONS {
        int id PK
        string task_id
        string expected_patient_id
        string scanned_patient_id
        string expected_kit_id
        string scanned_kit_id
        string result
        text message
        string created_at
    }
    TASK_STATE_TRANSITIONS {
        int id PK
        string task_id
        string request_id
        string from_state
        string to_state
        string trigger_type
        string triggered_by
        text reason
        string occurred_at
    }
    ROBOT_EVENTS {
        int id PK
        string request_id
        string task_id
        string timestamp
        string event_type
        text message
    }
```

- **care_requests**: 患者リクエスト自体（何を・誰が・いつ）。ロボットワークフローの状態は持たない。
- **robot_tasks**: リクエストに対する実際のロボット実行（1タスク=1行、`state`が`robot_service.py`のステートマシン値）。ロボット単位（`robot_id`）で非終端状態（IDLE/COMPLETED以外）のタスクは同時に1件まで、という同時実行制約がある。
- **kit_verifications**: QR照合の**試行**ごとの1行（OK/NG問わず）。`patient_id`/`kit_id`は後方互換のためのエイリアスで、常に`scanned_patient_id`/`scanned_kit_id`と同じ値が書き込まれる。`expected_*`と`scanned_*`を分けることで、患者違いなのかキット違いなのかをフリーテキストの`message`を読まなくても判別できる（PR9）。
- **task_state_transitions**: `robot_tasks.state`が変化するたびの構造化された履歴（PR8）。`robot_events`が人間が読むログなのに対し、こちらは`trigger_type`/`triggered_by`を使って集計しやすくした分析用の記録（`/analytics/state-durations`が利用）。
- **robot_events**: 看護師ダッシュボードのログ表示に使う、人間可読なイベントログ。

---

## 📊 Analytics API（PR10、PR11）

いずれも認証不要（GET専用、`/logs`などの読み取り専用ルートと同じ扱い）。実データの数値を見るには、先に「デモデータ」セクションのseedスクリプトを実行するか、UI/curlで実際にリクエストをいくつか流す。

| Method | Path | 説明 |
|--------|------|------|
| GET | `/analytics/summary` | 件数系の集計（総リクエスト数・完了/キャンセル数・エラータスク数・QR照合失敗率・平均完了時間） |
| GET | `/analytics/verification-failures` | QR照合NGの件数を失敗理由（`message`）別に集計 |
| GET | `/analytics/state-durations` | 各ロボット状態の平均滞在時間（`task_state_transitions`から算出、進行中で未確定の区間は除外） |

### デモウォークスルー（seed → 起動 → curl）

```bash
# 1. バックエンドを起動（別ターミナル）
uvicorn backend.main:app --reload --port 8000

# 2. デモデータを投入（--seedで再現可能な乱数シードを固定できる）
python -m backend.scripts.seed_demo_data --days 7 --tasks 20 --seed 42

# 3. Analytics APIを確認
curl http://localhost:8000/analytics/summary
curl http://localhost:8000/analytics/verification-failures
curl http://localhost:8000/analytics/state-durations
```

`/analytics/summary`のレスポンス例（値は実行のたびに変わる）:

```json
{
  "total_requests": 20,
  "completed_requests": 9,
  "cancelled_requests": 4,
  "error_tasks": 2,
  "verification_attempts": 11,
  "verification_failure_rate": 0.1818,
  "average_completion_seconds": 3.4
}
```

`/analytics/verification-failures`のレスポンス例:

```json
[
  { "failure_type": "patient_id mismatch", "count": 2 },
  { "failure_type": "kit_id mismatch", "count": 1 }
]
```

```bash
# 4. 使い終わったら削除（確認プロンプトあり、--yesでスキップ）
python -m backend.scripts.reset_demo_data --yes
```

---

## 🔌 API エンドポイント

| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| GET | `/state` | - | 現在の状態 |
| GET | `/requests` | - | リクエスト一覧（現状は最大1件） |
| POST | `/requests` | - | 患者リクエスト作成 |
| GET | `/requests/{id}` | - | リクエスト詳細 |
| POST | `/requests/{id}/cancel` | - | 患者キャンセル |
| POST | `/tasks/{id}/transition` | 🔒 | 状態遷移 |
| POST | `/tasks/{id}/verify` | 🔒 | QR照合 |
| POST | `/tasks/{id}/emergency-stop` | 🔒 | 緊急停止 |
| POST | `/tasks/{id}/reset` | 🔒 | リセット |
| POST | `/tasks/{id}/cancel` | 🔒 | 看護師キャンセル |
| GET | `/logs` | - | ログ |
| GET | `/analytics/summary` | - | 件数系の集計 |
| GET | `/analytics/verification-failures` | - | QR照合失敗の内訳 |
| GET | `/analytics/state-durations` | - | 状態別の平均滞在時間 |

🔒 = x-nurse-token ヘッダー必須

---

## ⚠️ Current Limitations

- 1ロボットにつき同時にアクティブなタスクは1件まで（`robot_id`単位。デフォルトロボットは1台のみ運用中）
- PostgreSQL/SQLAlchemy永続化（`care_requests`/`robot_tasks`/`kit_verifications`/`robot_events`/`task_state_transitions`）。テーブル間のリレーションはアプリケーション側で保証しており、DBレベルの外部キー制約は未設定
- QR照合はダッシュボード上でシミュレート
- 物理制御・ナビゲーションは未実装
- Dockerイメージはローカル/デモ用のcomposeスタック向けで、本番デプロイ向けの構成（secrets管理、`alembic upgrade head`の明示実行など）は別途必要
- 本プロトタイプは医療機器ではありません

---

## 📋 Roadmap

| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1–2 | API設計・UI分離・ステートマシン | ✅ |
| Phase 3 | PostgreSQL化・タスクリソースモデル・Perception・合成QRデモ・評価ベンチマーク・CI/品質整備 | ✅ |
| Phase 3.5 | 状態遷移履歴・QR照合詳細化・Analytics API・デモデータ・Docker化・README刷新（pytest 133件） | ✅ |
| Phase 4 | PyBulletシミュレーション・実カメラ対応 | 📋 |
| Phase 5 | 実機MVP・LeRobot | 📋 |

---

## License

MIT License
