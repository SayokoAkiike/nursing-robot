# PreCareBot — 看護現場の安全制約つきワークフロー（ソフトウェアMVP）

[![pytest](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml/badge.svg?branch=phase1-phase2)](https://github.com/SayokoAkiike/nursing-robot/actions/workflows/pytest.yml)

> **Software-only prototype — not a medical device, not for production use.**

PreCareBot は、看護現場の転倒予防を目的とした「安全制約つきベッドサイドアシストロボット」の**ソフトウェアMVP**です。
物理ロボットは実装しておらず、患者リクエスト受信・キット配送・QR照合・看護師確認というワークフローを、ステートマシンとREST APIで設計・実装しています。Phase 4からは、この一連のフローをヘッドレスなPyBullet物理シミュレーション上でも一気通貫で駆動できるようになりました。

Phase 4.5（PR22〜PR28）からは、これに加えてもう一つの方向性を持つソフトウェアになっています。PreCareBotは、患者が自分でボタンを押すことだけを前提にしたリクエスト端末ではなく、病棟内を巡回しながら患者に声掛けを行い、困りごとや転倒リスクにつながる訴えを拾い、必要に応じて看護師へ要点付きで通知する見守り・巡回支援ワークフローのソフトウェアMVPです。ベッドサイドのタブレットUIは、患者からの能動的な入力や、ロボット到着後の「立ち上がらずお待ちください」などの安全表示として併用できます。既存の配送ワークフローは変更・削除しておらず、巡回セッションの中で「配送が必要」と分類された場合のみ、既存のQR照合・看護師確認ゲート付き配送フローへそのまま接続します。

---

## 🎯 解決する問題

病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして転倒するリスクがある。特に高齢患者、認知機能が低下している患者、遠慮して訴えない患者は、そもそも自分からナースコールやタブレットを押してくれるとは限らない。

**設計アプローチ**: 看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。キットは看護師が確認・承認するまで開放しない（安全制約）。これに加えて、ロボットが病棟内を巡回して患者に声掛けし、困りごとを能動的に拾い上げ、必要に応じて看護師へ要点付きで通知する（Phase 4.5）。

---

## 🏗️ アーキテクチャ

```mermaid
flowchart LR
    UI["Streamlit UI\n(患者/看護師)"] -->|HTTP| API["FastAPI routes"]
    Perception["perception/\n(QRクライアント)"] -->|HTTP| API
    Sim["simulation層\nperception/pybullet_source.py\n(ヘッドレスPyBullet)"] --> Perception
    Runner["backend/scripts/\nrun_simulated_delivery.py"] -->|HTTP| API
    Runner --> Perception
    API --> WF["workflow_service\n(orchestration)"]
    WF --> RS["robot_service\n(状態遷移ルール, I/Oなし)"]
    WF --> VS["verification_service"]
    WF --> Repo["repositories.py"]
    Repo --> DB[("SQLite / PostgreSQL")]
    WF -.->|"_log()"| Events["robot_events\n(人間可読ログ)"]
    WF -.->|"_record_transition()"| Trans["task_state_transitions\n(分析用監査証跡)"]
    Events --> LogsAPI["/logs"]
    Trans --> Analytics["analytics_service\n→ /analytics/*"]
```

`perception/pybullet_source.py`は、既存の`perception/camera_source.py`が定義する「フレームを`.frames()`で流すだけ」というインターフェースをそのまま実装しているだけなので、`perception/run_perception.py`や`perception/qr_detector.py`は本物のWebカメラ・合成動画・PyBulletシミュレーションのどれが相手でも一切コードを変えずに動きます。`run_simulated_delivery.py`もこの`perception`層と、状態遷移用のHTTP API(`VerificationClient`)を組み合わせているだけで、独自の照合・状態遷移ロジックは持ちません。

### 巡回・見守りワークフローのアーキテクチャ（Phase 4.5）

```mermaid
flowchart TB
    Sim2["backend/scripts/\nrun_simulated_rounding.py"] -->|HTTP| API2["/rounding/*, /escalations/*"]
    API2 --> RoundSvc["rounding_service\n(状態遷移: ROUNDING_ALLOWED_TRANSITIONS)"]
    RoundSvc --> NeedSvc["need_classification_service\n(ルールベース分類, 純粋関数)"]
    RoundSvc --> EscSvc["escalation_service\n(看護師ack)"]
    RoundSvc -->|"DELIVERY_REQUIRED時のみ"| WF2["workflow_service\n(既存の配送フロー)"]
    RoundSvc --> Repo2["repositories.py"]
    EscSvc --> Repo2
    Repo2 --> DB2[("rounding_sessions\npatient_interactions\nnurse_escalations")]
    RoundSvc -.->|"_log()"| Events2["robot_events\n(既存ログと共用)"]
    EscSvc --> NurseUI["ui/nurse_dashboard\nEscalationsセクション"]
    RoundSvc --> PatientUI["ui/patient_request_app\n(通知/安全表示)"]
    Repo2 --> Analytics2["analytics_service\n→ /analytics/rounding-summary\n→ /analytics/escalation-breakdown"]
```

`rounding_service`の状態遷移ルール（`ROUNDING_ALLOWED_TRANSITIONS`）は、既存の配送フロー用`ALLOWED_TRANSITIONS`とは意図的に別辞書として`robot_service.py`に定義されています。両者を1つの辞書にまとめてしまうと、片方のワークフロー変更がもう片方の安全ゲート（`VERIFYING_PATIENT`→`DOCKING`のQR照合限定・`KIT_RELEASED`の看護師確認限定など）に気づかないまま影響してしまうリスクがあるためです。2つのワークフローが交わるのは、巡回中に「配送が必要」と分類された（`DELIVERY_REQUIRED`）ときの1点だけで、そこから先は既存の配送フローがそのまま引き継ぎます。

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
| ヘッドレスPyBulletシミュレーション（ドック→ベッドサイド移動、QRオーバーレイ、既存perceptionパイプラインでの照合） | `perception/pybullet_source.py` | ✅ |
| シミュレーション配送フロー一括駆動（安全確認ゲートは既定で人間待ち） | `backend/scripts/run_simulated_delivery.py` | ✅ |
| DB整合性制約（DateTime統一・FK・ロボット単位同時タスク数の部分ユニークインデックス） | `backend/db/models.py`, `alembic/` | ✅ |
| Grafanaダッシュボード（Analytics APIと同内容をSQLで可視化、`docker-compose up`で自動プロビジョニング） | `grafana/provisioning/` | ✅ |
| PyBullet GUIでのローカル目視デモ | `backend/scripts/run_gui_demo.py` | ✅ |
| 巡回・見守りワークフロー用ドメインモデル（rounding_sessions/patient_interactions/nurse_escalations、care_requestsへのsource/rounding_session_id追加） | `backend/db/models.py`, `alembic/` | ✅ |
| 巡回状態遷移ルール・ルールベース要望分類・看護師エスカレーションのオーケストレーション | `backend/services/rounding_service.py`, `backend/services/need_classification_service.py`, `backend/services/escalation_service.py` | ✅ |
| 巡回・エスカレーションAPI（`/rounding/*`、`/escalations/*`） | `backend/api/routes_rounding.py`, `backend/api/routes_escalations.py` | ✅ |
| 巡回シミュレーション一括駆動（6シナリオ、看護師確認ゲートは既定で人間待ち） | `backend/scripts/run_simulated_rounding.py` | ✅ |
| 看護師ダッシュボードEscalationsセクション・患者UI安全表示更新 | `ui/nurse_dashboard/app.py`, `ui/patient_request_app/app.py` | ✅ |
| 巡回Analytics API・Grafanaダッシュボード（セッション概況・エスカレーションキュー） | `backend/services/analytics_service.py`, `grafana/provisioning/dashboards/rounding-overview.json`, `escalation-queue.json` | ✅ |
| 品質管理（ruff / mypy / pytest-cov / CI） | `ruff.toml`, `mypy.ini`, `.coveragerc`, `.github/workflows/pytest.yml` | ✅ |
| ドメイン登録テーブル（Hospital/Ward/Room/Bed/Patient/Nurse/Robot、読み取り専用API、シードスクリプト） | `backend/db/models.py`, `backend/services/domain_service.py`, `backend/api/routes_domain.py`, `backend/scripts/seed_domain_data.py` | ✅ |
| マルチロボット対応（配送ワークフローの`robot_id`パラメータ化、ロボット単位のIDLE/BUSYステータス、巡回セッションの担当ロボットへの配送引き継ぎ） | `backend/services/workflow_service.py`, `backend/services/rounding_service.py`, `backend/services/domain_service.py`, `backend/api/routes_requests.py`, `backend/api/routes_domain.py` | ✅ |
| UIのリアルタイム更新（`st.experimental_fragment(run_every=...)`による部分自動更新、ブロッキングsleepポーリングの撤去） | `ui/patient_request_app/app.py`, `ui/nurse_dashboard/app.py` | ✅ |
| pytest テスト（300件） | `tests/` （API/workflow service/state machine/repositories/verification/perception/vision/analytics/Docker設定/PyBulletシミュレーション/Grafana設定/GUIデモ/巡回ワークフロー/ドメイン登録/マルチロボット/UIリアルタイム更新） | ✅ |

## ❌ 未実装（今後の予定）

| 機能 | 状況 | 予定フェーズ |
|------|------|------------|
| 実カメラでのリアルタイムQRスキャン | 合成動画/画像ディレクトリ/PyBulletシミュレーション入力では検証済み。実機Webカメラでの動作は未検証（`WebcamSource`自体はCodespacesのような画面なし環境では動かせない） | Phase 4 |
| ロボットの物理制御・ナビゲーション | PyBulletシーン内では`resetBasePositionAndOrientation`で位置を直接設定しているのみで、ホイールや関節による本物の駆動制御はまだ無い | Phase 4 |
| 巡回ワークフローの実音声認識・実人物検出・LLMベースの要望分類 | 現状はシミュレーション/疑似入力（`input_mode="simulated"`）とルールベース分類のみ。当初の設計方針として意図的にスコープ外としている | Phase 5以降 |
| マルチロボット・複数病棟対応 | 未着手 | Phase 5 |

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

`db`（`postgres:16-alpine`）・`backend`（このリポジトリの`Dockerfile`からビルドしたFastAPI）・`grafana`（`grafana-oss`、`db`宛のPostgreSQLデータソースとダッシュボード3枚を自動プロビジョニング、PR16）の3サービスが、`db`のヘルスチェック通過を待ってから`backend`/`grafana`が起動する。バックエンドは `http://localhost:8000` で待ち受け（Swagger UIは `/docs`）。Grafanaは `http://localhost:3000` （admin/admin、または匿名Viewerアクセス）で、手動セットアップなしに「PreCareBot」フォルダにダッシュボードが最初から表示される。UI（Streamlit）はcomposeに含めていないので、必要ならローカルで別途起動する（上のQuick Start参照、`DATABASE_URL`を`.env`で`postgresql+psycopg2://precare:precare@localhost:5432/precare`に向ければ同じDBを共有できる）。

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

`backend/db/models.py`で定義される8テーブル。タイムスタンプ列は全て`DateTime`型（PR15でSQLite/PostgreSQL両対応のまま`String`から統一）。以下のER図が示す`request_id`/`task_id`はSQLAlchemyレベルの`ForeignKey`制約として実際に強制されており（PR15）、`robot_tasks`には「ロボット単位で非終端状態のタスクは同時に1件まで」という安全制約を守るための部分ユニークインデックス（`UNIQUE(robot_id) WHERE state NOT IN ('IDLE','COMPLETED','ERROR')`）も張られている。

```mermaid
erDiagram
    CARE_REQUESTS ||--o{ ROBOT_TASKS : "request_id"
    ROBOT_TASKS ||--o{ KIT_VERIFICATIONS : "task_id"
    ROBOT_TASKS ||--o{ TASK_STATE_TRANSITIONS : "task_id"
    CARE_REQUESTS ||--o{ ROBOT_EVENTS : "request_id"
    ROBOT_TASKS ||--o{ ROBOT_EVENTS : "task_id"
    ROUNDING_SESSIONS ||--o{ PATIENT_INTERACTIONS : "rounding_session_id"
    ROUNDING_SESSIONS ||--o{ NURSE_ESCALATIONS : "rounding_session_id"
    ROUNDING_SESSIONS ||--o{ CARE_REQUESTS : "rounding_session_id"
    CARE_REQUESTS ||--o{ NURSE_ESCALATIONS : "request_id"

    CARE_REQUESTS {
        string id PK
        string patient_id
        string request_type
        string priority
        string status
        datetime created_at
        datetime completed_at
        string source
        string rounding_session_id FK
    }
    ROBOT_TASKS {
        string id PK
        string request_id
        string robot_id
        string state
        string kit_id
        datetime assigned_at
        datetime updated_at
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
        datetime created_at
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
        datetime occurred_at
    }
    ROBOT_EVENTS {
        int id PK
        string request_id
        string task_id
        datetime timestamp
        string event_type
        text message
    }
    ROUNDING_SESSIONS {
        string id PK
        string robot_id
        string room
        string patient_id
        string status
        datetime started_at
        datetime ended_at
        text interaction_summary
        string detected_need
        string escalation_level
        datetime created_at
        datetime updated_at
    }
    PATIENT_INTERACTIONS {
        int id PK
        string rounding_session_id FK
        string patient_id
        string room
        text prompt
        text patient_response
        string input_mode
        string detected_need
        string confidence
        datetime created_at
    }
    NURSE_ESCALATIONS {
        string id PK
        string rounding_session_id FK
        string request_id FK
        string patient_id
        string room
        text summary
        string priority
        text reason
        text suggested_action
        string status
        datetime created_at
        datetime acknowledged_at
        string acknowledged_by
    }
```

- **care_requests**: 患者リクエスト自体（何を・誰が・いつ）。ロボットワークフローの状態は持たない。`source`（`patient_tablet`/`robot_rounding`/`nurse_manual`/`demo_seed`）と`rounding_session_id`（nullable）はPhase 4.5で追加され、リクエストが患者タブレット由来か巡回セッション由来かを区別する。
- **robot_tasks**: リクエストに対する実際のロボット実行（1タスク=1行、`state`が`robot_service.py`のステートマシン値）。ロボット単位（`robot_id`）で非終端状態（IDLE/COMPLETED以外）のタスクは同時に1件まで、という同時実行制約がある。
- **kit_verifications**: QR照合の**試行**ごとの1行（OK/NG問わず）。`patient_id`/`kit_id`は後方互換のためのエイリアスで、常に`scanned_patient_id`/`scanned_kit_id`と同じ値が書き込まれる。`expected_*`と`scanned_*`を分けることで、患者違いなのかキット違いなのかをフリーテキストの`message`を読まなくても判別できる（PR9）。
- **task_state_transitions**: `robot_tasks.state`が変化するたびの構造化された履歴（PR8）。`robot_events`が人間が読むログなのに対し、こちらは`trigger_type`/`triggered_by`を使って集計しやすくした分析用の記録（`/analytics/state-durations`が利用）。
- **robot_events**: 看護師ダッシュボードのログ表示に使う、人間可読なイベントログ。巡回ワークフローのイベントもここに記録され、既存のログ表示と統合される。
- **rounding_sessions**（Phase 4.5）: ロボットが病棟内を1回巡回する単位。`status`は`ROUNDING_ALLOWED_TRANSITIONS`（配送用`ALLOWED_TRANSITIONS`とは別辞書）の値を持つ。
- **patient_interactions**（Phase 4.5）: 巡回セッション内の声掛け・応答1回ごとの記録。`detected_need`/`confidence`はルールベース分類（`need_classification_service.py`）の結果。
- **nurse_escalations**（Phase 4.5）: 看護師へ通知すべき内容のキュー。`request_id`はnullable（配送を伴わない純粋な通知もある）。

### ドメイン登録テーブル（Hospital/Ward/Room/Bed/Patient/Nurse/Robot）

`backend/core/config.py`の`PATIENTS`辞書（患者2名分をハードコード）に加えて、`hospitals` / `wards` / `rooms` / `beds` / `patients` / `nurses` / `robots`の7テーブルを追加し、病院組織構造を実データとして持てるようにした。既存の`care_requests`/`robot_tasks`/`rounding_sessions`などが使う`patient_id`/`robot_id`/`room`は引き続きプレーンな文字列のままで、このテーブル群へのFK化はしていない（安全制約に関わる配送・巡回フローのテスト全体に影響する変更のため、意図的に別PRへ切り出す）。`backend/services/domain_service.py`の`seed_default_domain_data()`が、既存の`PATIENTS`辞書と`workflow_service.DEFAULT_ROBOT_ID`と同じ内容（病院1・病棟1・患者2名分の部屋とベッド・看護師1名・ロボット1台）を投入し、`python -m backend.scripts.seed_domain_data`で明示的に実行できる（`seed_demo_data.py`と同じく自動実行はしない）。読み取り専用の`GET /patients`・`GET /patients/{id}`・`GET /robots`・`GET /wards`（病棟→部屋→ベッド→入居患者のネスト構造）で参照できる。

### マルチロボット対応

`robot_tasks`にはPR15の時点で「ロボット単位（`robot_id`）で非終端状態のタスクは同時に1件まで」という部分ユニークインデックス（`ux_robot_tasks_active_robot`）がすでに張られており、データモデルとしては複数ロボットに以前から対応していた。ただし配送フロー側の`workflow_service.py`はその上で常に`DEFAULT_ROBOT_ID`（`"ROBOT_1"`）1台にしか実際には割り当てておらず、`tests/test_workflow_service.py::test_concurrency_guard_is_per_robot_not_global`がそのギャップを自らのコメントで明記していた。今回、そのギャップをサービス層で解消した。

- `workflow_service.create_request()` / `get_current_state()`が任意の`robot_id`引数を取るようになった（未指定時は従来どおり`DEFAULT_ROBOT_ID`、既存呼び出し元の挙動は変わらない）。
- `_view()`が返す辞書に`robot_id`が追加され、`GET /requests` / `GET /requests/{id}` / `GET /state`のレスポンス、および看護師ダッシュボードのタスク表示行から、どのロボットのタスクかが分かるようになった。
- `POST /requests`（`RequestCreate`スキーマ）が`robot_id`を任意項目として受け付ける（`RoundingStart.robot_id`と同じパターン）。
- `rounding_service.require_delivery()`が、巡回セッション自身の`robot_id`（`start_rounding()`で指定されたロボット）を配送タスクへそのまま引き継ぐようになった。これまでは巡回ロボットが`ROBOT_2`であっても、配送タスクは常に`DEFAULT_ROBOT_ID`（`ROBOT_1`）へ暗黙に割り当てられていた。
- `domain_service.list_robots_view()`が、登録済みの各ロボットに`repositories.get_active_task_for_robot()`由来のライブな`status`（`IDLE`/`BUSY`）を付与して返す。`GET /robots`のレスポンスに反映され、`domain_service.pick_available_robot_id()`（空いているロボットのidを1台返す、全て稼働中なら`None`）の土台にもなっている。

### UIのリアルタイム更新

患者用タブレットUI・看護師ダッシュボードは、どちらも従来`time.sleep(3); st.rerun()`でスクリプト全体をブロックしてから丸ごと再実行・再描画する自前ポーリングだった（患者UIは待機中/エスカレーション中は常時、看護師ダッシュボードは「Auto-refresh」チェックボックスON時のみ）。これを`st.experimental_fragment(run_every=2)`（安定版`st.fragment`に相当する、streamlit 1.35.0時点でのAPI名）に置き換え、各セクション（看護師ダッシュボードのEscalations/タスク一覧/ログ、患者UIの画面全体）がそれぞれ独立したタイマーで自動的に部分再描画されるようにした。ポイントは以下の3点。

- 看護師ダッシュボードの自動更新は常時ON（チェックボックス不要）になり、他のセクションを巻き込まずにEscalations・タスク一覧・ログがそれぞれ独立して更新される。
- 患者UIは「選択画面」「待機画面」「完了/エラー画面」の3状態すべてを1つのフラグメントが毎回組み立て直すため、ボタン操作以外の理由（看護師によるリセット、巡回からのエスカレーション）で状態が変わった場合でも自動的に追従する。
- 新規の外部依存は追加していない（`streamlit==1.35.0`に元々含まれる機能）。ロードマップの当初の呼称は「WebSocket化」だったが、生のWebSocketクライアントをStreamlitのスクリプト再実行モデルへ手動で統合するのはバックグラウンドスレッドの管理などで壊れやすく、`st.experimental_fragment`の部分自動更新の方が保守性が高いと判断した。体感としては「短間隔ポーリング」のままであり、サーバー側からの即時プッシュ通知ではない点は変わらない。

---

## 📊 Analytics API（PR10、PR11）

いずれも認証不要（GET専用、`/logs`などの読み取り専用ルートと同じ扱い）。実データの数値を見るには、先に「デモデータ」セクションのseedスクリプトを実行するか、UI/curlで実際にリクエストをいくつか流す。

| Method | Path | 説明 |
|--------|------|------|
| GET | `/analytics/summary` | 件数系の集計（総リクエスト数・完了/キャンセル数・エラータスク数・QR照合失敗率・平均完了時間） |
| GET | `/analytics/verification-failures` | QR照合NGの件数を失敗理由（`message`）別に集計 |
| GET | `/analytics/state-durations` | 各ロボット状態の平均滞在時間（`task_state_transitions`から算出、進行中で未確定の区間は除外） |
| GET | `/analytics/rounding-summary` | 巡回セッション数・患者発見数・要望分類数・エスカレーション数・URGENT件数・平均ack時間（Phase 4.5） |
| GET | `/analytics/escalation-breakdown` | `nurse_escalations`をpriority別/detected_need別/status別に集計（Phase 4.5） |

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

`/analytics/rounding-summary`のレスポンス例（値は実行のたびに変わる）:

```json
{
  "total_rounding_sessions": 6,
  "patients_detected": 6,
  "interactions_started": 6,
  "needs_classified": 6,
  "escalations_created": 4,
  "urgent_escalations": 1,
  "average_time_to_ack": 2.3
}
```

`/analytics/escalation-breakdown`のレスポンス例:

```json
{
  "by_priority": [
    { "priority": "HIGH", "count": 2 },
    { "priority": "URGENT", "count": 1 },
    { "priority": "MEDIUM", "count": 1 }
  ],
  "by_detected_need": [
    { "detected_need": "toileting", "count": 2 },
    { "detected_need": "pain", "count": 1 },
    { "detected_need": "water", "count": 1 }
  ],
  "by_status": [
    { "status": "ACKNOWLEDGED", "count": 3 },
    { "status": "PENDING", "count": 1 }
  ]
}
```

```bash
# 4. 使い終わったら削除（確認プロンプトあり、--yesでスキップ）
python -m backend.scripts.reset_demo_data --yes
```

---

## 📈 モニタリング（Grafana、PR16）

`docker-compose up`すると、`/analytics/*`と同じ内容をSQLで直接可視化するGrafanaダッシュボードが5枚、手動セットアップなしで最初から使える状態になる（`grafana/provisioning/`でPostgreSQLデータソースとダッシュボードJSONを自動プロビジョニング）。

| ダッシュボード | 内容 |
|---------------|------|
| 完了/キャンセル数の推移 | `care_requests`を日次集計した完了・キャンセル件数の推移 |
| QR照合失敗率 | `kit_verifications`の全体NG率＋失敗理由（`message`）別の内訳 |
| 状態別平均滞在時間 | `task_state_transitions`に対する`LEAD()`ウィンドウ関数で、`/analytics/state-durations`と同じロジックをSQLで再現 |
| 巡回セッション概況（Phase 4.5） | 巡回セッション数・患者発見数・要望分類数・エスカレーション数・URGENT件数・平均ack時間、日次セッション数の推移 |
| エスカレーションキュー（Phase 4.5） | 未確認(PENDING)件数・平均ack時間、priority別/need別の内訳（円グラフ）、status別件数（テーブル） |

```bash
docker-compose up --build
python -m backend.scripts.seed_demo_data --days 14   # ダッシュボードに表示するデータが要る場合
```

`http://localhost:3000` を開く（admin/adminでログイン、または匿名Viewerアクセスでもダッシュボード閲覧は可能）。

---

## 🤖 シミュレーション（Phase 4）

物理ロボットは無いが、ヘッドレスPyBullet(`p.DIRECT`、画面表示なしでCI/Codespacesでも動く)上でドック位置からベッドサイド位置まで移動する簡易な物理シーンを組み、そこで撮影したフレームを既存のperceptionパイプライン(`perception/qr_detector.py`)にそのまま流し込んで照合できる。

`perception/pybullet_source.py`は`perception/camera_source.py`の`FrameSource`インターフェース(`.frames()`でBGRフレームを返す)をそのまま実装しているだけなので、`--source`に渡す文字列を変えるだけで実機Webカメラ・合成動画・PyBulletシミュレーションを切り替えられる。

```bash
python -m perception.run_perception \
  --request-id <既存のリクエストID> \
  --source pybullet:delivery_with_qr \
  --base-url http://localhost:8000 \
  --nurse-token $NURSE_TOKEN
```

QRコードは3D物体へのテクスチャ貼り付けではなく、レンダリング後のフレームに2D画像として合成している（PyBulletのUVマッピング/ライティングに依存させず、`cv2.QRCodeDetector`が確実に読み取れる解像度で毎フレーム描画するため）。

### 配送フロー一括駆動（`backend/scripts/run_simulated_delivery.py`）

リクエスト作成からQR照合・状態遷移までを、本物のAPI(`perception/verification_client.py`)越しに一気通貫で実行する開発・デモ用スクリプト。`seed_demo_data.py`と同じく、明示的にコマンドを実行したときだけ動く。

```bash
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN
```

**安全上の設計**: `WAITING_FOR_NURSE_CONFIRMATION`（キット開放前の看護師確認）に到達すると、このスクリプトは既定では**そこで止まり、人間の確認を待つ**。ナースダッシュボードで実際に確認するか、表示されるcurlコマンドを手動で叩く必要がある。`--auto-confirm`を明示的に付けたときだけスクリプト自身がこのボタンを押すが、これは「有効なナーストークンを持つ誰か/何かがAPIを呼ぶ」という、ダッシュボードが行っているのと全く同じ操作をコマンドラインから行っているだけであり、フラグを付けるという行為自体が人間の意思表示にあたる。`tests/test_run_simulated_delivery.py`にはこのゲートが既定では回避されないことを保証する回帰テストがある。

```bash
# 看護師確認を自動で行う場合（デモ・CI向け）
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN --auto-confirm
```

### 巡回・見守りワークフロー一括駆動（`backend/scripts/run_simulated_rounding.py`、Phase 4.5）

実際の人物検出・音声認識は行わず（Phase 4.5の設計方針どおり）、7つの名前付きシナリオ（`rounding_normal` / `rounding_patient_detected` / `rounding_toileting_escalation` / `rounding_water_request` / `rounding_no_need` / `rounding_urgent_pain` / `rounding_fall_risk`）それぞれに紐づく疑似患者応答を、本物のAPI（`/rounding/*`、`/escalations/*`）越しに一気通貫で流す開発・デモ用スクリプト。分類結果（`detected_need`/`escalation_level`）を期待値と照合するので、単なるデモではなく`need_classification_service`のルールセットに対するE2Eスモークテストも兼ねる。`rounding_fall_risk`は本製品が最も防ぎたい状況（患者が看護師を待たず一人でふらついて立ち上がってしまう）を再現するシナリオで、`fall_risk`はpainと同じURGENT/URGENT_ESCALATIONだが、通常のトイレ希望（toileting/HIGH）より優先されるようルール順で明示的に上位に置かれている。

```bash
python -m backend.scripts.run_simulated_rounding --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN
```

**安全上の設計**: `run_simulated_delivery.py`と全く同じ思想。エスカレーションが発生するシナリオ（`NURSE_NOTIFICATION`/`URGENT_ESCALATION`ルート）では、このスクリプトは既定では`WAITING_FOR_NURSE_ACK`で**止まり、人間の確認を待つ**（タイムアウトすると、手動で叩けるcurlコマンドを表示してエラー終了する）。`--auto-ack`を明示的に付けたときだけスクリプト自身がこのボタンを押す。`INFORMATION_ONLY`ルート（`rounding_normal`/`rounding_no_need`）はそもそも看護師ゲートが無いので、`--auto-ack`の有無に関わらず常に`COMPLETED`まで進む。`tests/test_run_simulated_rounding.py`にはこのゲートが既定では回避されないことを保証する回帰テストがある。

```bash
# 看護師確認を自動で行う場合（デモ・CI向け）
python -m backend.scripts.run_simulated_rounding --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN --auto-ack
```

### ローカルGUIデモ（`backend/scripts/run_gui_demo.py`、PR20）

上記は全てヘッドレス（`p.DIRECT`、画面表示なし）で、CI/Codespacesでも動く。ロボットが実際に動く様子を画面で見たい場合は、ディスプレイのあるローカルマシン限定で以下を実行する（**Codespacesでは動かない**）。

```bash
python -m backend.scripts.run_gui_demo
python -m backend.scripts.run_gui_demo --steps 200 --speed 2.0
```

PyBulletのGUIウィンドウが開き、ドック位置からベッドサイド位置までロボットが移動する様子を見られる。QRオーバーレイはレンダリング後のフレームへの2D合成であり、ライブのGUIウィンドウには映らない（見た目のデモ専用で、`perception`パイプラインは通らない。QR照合込みの動作確認は`run_simulated_delivery.py`を使う）。

---

## 🔌 API エンドポイント

| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| GET | `/state?robot_id=` | - | 現在の状態（`robot_id`省略時はデフォルトロボット） |
| GET | `/requests` | - | リクエスト一覧（各行に`robot_id`を含む） |
| POST | `/requests` | - | 患者リクエスト作成（任意で`robot_id`を指定可能） |
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
| POST | `/rounding/start` | - | 巡回セッション開始 |
| GET | `/rounding/{id}` | - | 巡回セッション詳細 |
| POST | `/rounding/{id}/detect-patient` | - | 患者発見 |
| POST | `/rounding/{id}/start-interaction` | - | 声掛け開始（プロンプト取得） |
| POST | `/rounding/{id}/classify-need` | - | 患者応答の登録・要望分類 |
| POST | `/rounding/{id}/provide-information` | - | 情報提供のみで完了（エスカレーション不要時） |
| POST | `/rounding/{id}/escalate` | - | 看護師エスカレーション作成 |
| POST | `/rounding/{id}/require-delivery` | - | 配送フローへ接続（既存の配送ワークフローに合流） |
| GET | `/escalations` | - | エスカレーション一覧（PENDING優先） |
| GET | `/escalations/{id}` | - | エスカレーション詳細 |
| POST | `/escalations/{id}/ack` | 🔒 | 看護師確認 |
| GET | `/analytics/rounding-summary` | - | 巡回ワークフローの件数系集計 |
| GET | `/analytics/escalation-breakdown` | - | エスカレーションのpriority/need/status別内訳 |
| GET | `/patients` | - | 患者一覧（ドメイン登録テーブル、room_number/ward_name/allowed_kits付き） |
| GET | `/patients/{id}` | - | 患者詳細 |
| GET | `/robots` | - | ロボット一覧（各ロボットに`status`＝IDLE/BUSYを含む） |
| GET | `/wards` | - | 病棟一覧（部屋→ベッド→入居患者のネスト構造） |

🔒 = x-nurse-token ヘッダー必須

---

## ⚠️ Current Limitations

- 1ロボットにつき同時にアクティブなタスクは1件まで（`robot_id`単位）。配送・巡回とも複数ロボットへの割り当てはサービス層/APIとして可能になったが、「どの患者にどのロボットを自動で割り当てるか」（最寄りの空きロボットを選ぶ、等）は`domain_service.pick_available_robot_id()`という土台のみで、まだ呼び出し元には自動配線していない。デモのseedデータもロボット1台のみ
- PostgreSQL/SQLAlchemy永続化（`care_requests`/`robot_tasks`/`kit_verifications`/`robot_events`/`task_state_transitions`/`rounding_sessions`/`patient_interactions`/`nurse_escalations`）。テーブル間の外部キー制約とロボット単位の同時タスク数制約はDBレベルで強制（PR15）
- QR照合はダッシュボード上／PyBulletシミュレーション上でシミュレート
- 物理制御・ナビゲーションは未実装（PyBulletシーン内でも位置を直接設定しているのみ）
- Dockerイメージはローカル/デモ用のcomposeスタック向けで、本番デプロイ向けの構成（secrets管理、`alembic upgrade head`の明示実行など）は別途必要
- 巡回ワークフローは実音声認識・実人物検出を行わず、シミュレーション/疑似入力とルールベース分類のみ（LLMは使用していない）
- UIの自動更新は`st.experimental_fragment(run_every=2)`による短間隔（2秒）ポーリングであり、バックエンドからのイベントプッシュ（真のWebSocket/SSE）ではない
- 本プロトタイプは医療機器ではありません

---

## 📋 Roadmap

| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1–2 | API設計・UI分離・ステートマシン | ✅ |
| Phase 3 | PostgreSQL化・タスクリソースモデル・Perception・合成QRデモ・評価ベンチマーク・CI/品質整備 | ✅ |
| Phase 3.5 | 状態遷移履歴・QR照合詳細化・Analytics API・デモデータ・Docker化・README刷新 | ✅ |
| Phase 4 | ヘッドレスPyBulletシミュレーション基盤・QRオーバーレイ・配送フロー一括駆動・DB整合性制約（DateTime/FK/部分ユニークインデックス）・Grafanaダッシュボード・ローカルGUIデモ。実カメラ対応／物理制御（ホイール・関節）は未着手 | ✅ |
| Phase 4.5 | 巡回・見守りワークフロー（ドメインモデル・状態遷移・ルールベース要望分類・看護師エスカレーション・API・シミュレーション・ダッシュボード・Analytics/Grafana拡張、pytest 249件）。実音声認識・実人物検出は未着手 | ✅ |
| Phase 5 | 実機MVP・マルチロボット・LeRobot | 📋 |

---

## License

MIT License
