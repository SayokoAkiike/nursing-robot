PreCareBot — 看護現場の安全制約つきワークフロー（ソフトウェアMVP）

Software-only prototype — not a medical device, not for production use.

PreCareBot は、看護現場の転倒予防を目的とした「安全制約つきベッドサイドアシストロボット」のソフトウェアMVPです。 物理ロボットは実装しておらず、患者リクエスト受信・キット配送・QR照合・看護師確認というワークフローを、ステートマシンとREST APIで設計・実装しています。Phase 4からは、この一連のフローをヘッドレスなPyBullet物理シミュレーション上でも一気通貫で駆動できるようになりました。

🎯 解決する問題
病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして転倒するリスクがある。

設計アプローチ: 看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。キットは看護師が確認・承認するまで開放しない（安全制約）。

🏗️ アーキテクチャ
HTTP
HTTP
HTTP
_log()
_record_transition()
Streamlit UI(患者/看護師)
FastAPI routes
perception/(QRクライアント)
simulation層perception/pybullet_source.py(ヘッドレスPyBullet)
backend/scripts/run_simulated_delivery.py
workflow_service(orchestration)
robot_service(状態遷移ルール, I/Oなし)
verification_service
repositories.py
SQLite / PostgreSQL
robot_events(人間可読ログ)
task_state_transitions(分析用監査証跡)
/logs
analytics_service→ /analytics/*
perception/pybullet_source.pyは、既存のperception/camera_source.pyが定義する「フレームを.frames()で流すだけ」というインターフェースをそのまま実装しているだけなので、perception/run_perception.pyやperception/qr_detector.pyは本物のWebカメラ・合成動画・PyBulletシミュレーションのどれが相手でも一切コードを変えずに動きます。run_simulated_delivery.pyもこのperception層と、状態遷移用のHTTP API(VerificationClient)を組み合わせているだけで、独自の照合・状態遷移ロジックは持ちません。

📦 現在実装済み
機能	ファイル	状態
患者リクエストUI	ui/patient_request_app/app.py	✅
看護師ダッシュボード	ui/nurse_dashboard/app.py	✅
REST API (FastAPI)	backend/main.py	✅
ワークフロー・ステートマシン	robot_control/state_machine.py	✅
サービス層（ロボットタスクの実行・状態遷移）	backend/services/robot_service.py	✅
サービス層（リクエスト作成・キャンセル・照合・状態遷移履歴記録）	backend/services/workflow_service.py	✅
QRコード生成・照合	vision/qr_detection/	✅
イベントログ（workflow_service内_log()がrobot_eventsへ記録）	backend/services/workflow_service.py	✅
PostgreSQL/SQLAlchemy永続化 + Alembicマイグレーション	backend/db/, alembic/	✅
タスクリソースモデル（care_requests/robot_tasks/kit_verifications、ロボット単位の同時実行制約）	backend/db/models.py, backend/services/workflow_service.py	✅
状態遷移履歴（全state変化をtask_state_transitionsに記録）	backend/db/models.py, backend/services/workflow_service.py	✅
QR照合の期待値/実測値分離（expected_/scanned_）	backend/db/models.py, backend/services/workflow_service.py	✅
Analytics API（件数集計・照合失敗内訳・状態滞在時間）	backend/api/routes_analytics.py, backend/services/analytics_service.py	✅
デモデータ生成・リセット（開発・デモ用）	backend/scripts/seed_demo_data.py, backend/scripts/reset_demo_data.py	✅
Perceptionモジュール（複数フレーム確定QR検出＋照合APIクライアント）	perception/	✅
合成QRデモ動画生成（実写映像不使用）	vision/qr_detection/demo/	✅
QR検出の評価ベンチマーク（confirm_frames毎の検出成功率・所要フレーム数・不安定検出数）	perception/evaluate_detector.py	✅
バックエンドAPIのDocker化（docker-compose upでDB+APIを一括起動）	Dockerfile, docker-compose.yml	✅
ヘッドレスPyBulletシミュレーション（ドック→ベッドサイド移動、QRオーバーレイ、既存perceptionパイプラインでの照合）	perception/pybullet_source.py	✅
シミュレーション配送フロー一括駆動（安全確認ゲートは既定で人間待ち）	backend/scripts/run_simulated_delivery.py	✅
DB整合性制約（DateTime統一・FK・ロボット単位同時タスク数の部分ユニークインデックス）	backend/db/models.py, alembic/	✅
Grafanaダッシュボード（Analytics APIと同内容をSQLで可視化、docker-compose upで自動プロビジョニング）	grafana/provisioning/	✅
PyBullet GUIでのローカル目視デモ	backend/scripts/run_gui_demo.py	✅
品質管理（ruff / mypy / pytest-cov / CI）	ruff.toml, mypy.ini, .coveragerc, .github/workflows/pytest.yml	✅
pytest テスト（159件）	tests/ （API/workflow service/state machine/repositories/verification/perception/vision/analytics/Docker設定/PyBulletシミュレーション/Grafana設定/GUIデモ）	✅
❌ 未実装（今後の予定）
機能	状況	予定フェーズ
実カメラでのリアルタイムQRスキャン	合成動画/画像ディレクトリ/PyBulletシミュレーション入力では検証済み。実機Webカメラでの動作は未検証（WebcamSource自体はCodespacesのような画面なし環境では動かせない）	Phase 4
ロボットの物理制御・ナビゲーション	PyBulletシーン内ではresetBasePositionAndOrientationで位置を直接設定しているのみで、ホイールや関節による本物の駆動制御はまだ無い	Phase 4
マルチロボット・複数病棟対応	未着手	Phase 5
🚀 Quick Start
ローカル実行（venv、SQLiteフォールバック）
bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v
DATABASE_URLを.envで指定しない場合、data/precare.dbのSQLiteファイルにフォールバックする（pytestやちょっとした動作確認に十分、追加セットアップ不要）。

Docker実行（PR13、PostgreSQL + バックエンドAPI）
bash
docker-compose up --build
db（postgres:16-alpine）・backend（このリポジトリのDockerfileからビルドしたFastAPI）・grafana（grafana-oss、db宛のPostgreSQLデータソースとダッシュボード3枚を自動プロビジョニング、PR16）の3サービスが、dbのヘルスチェック通過を待ってからbackend/grafanaが起動する。バックエンドは http://localhost:8000 で待ち受け（Swagger UIは /docs）。Grafanaは http://localhost:3000 （admin/admin、または匿名Viewerアクセス）で、手動セットアップなしに「PreCareBot」フォルダにダッシュボードが最初から表示される。UI（Streamlit）はcomposeに含めていないので、必要ならローカルで別途起動する（上のQuick Start参照、DATABASE_URLを.envでpostgresql+psycopg2://precare:precare@localhost:5432/precareに向ければ同じDBを共有できる）。

bash
docker-compose down
で停止。NURSE_TOKEN / ALLOWED_ORIGINSはdocker-compose.yml内で環境変数展開されており、ホスト側で環境変数NURSE_TOKENを設定すればそちらが優先される（未設定時はdev用のデフォルト値）。

品質チェック（PR7）
bash
ruff check .
mypy backend perception vision
pytest tests/ --cov=backend --cov=perception --cov=vision --cov-report=term-missing
デモデータ（PR12、開発・デモ用 -- 本番では使わない）
Analytics API（/analytics/*）の中身を実データで確認するためのスクリプト。明示的にコマンドを実行したときだけ動作し、起動時に自動実行されることはない。ロボットにアクティブなタスクがある状態では拒否される（実行中タスクを壊さない）。

bash
# 直近7日間に散らばる20件の合成リクエストを生成（正常完了/患者・看護師キャンセル/QR照合NG/緊急停止/看護師確認待ちが長いケースを含む）
python -m backend.scripts.seed_demo_data --days 7 --tasks 20

# 生成したデータを全て削除（確認プロンプトあり。--yesでスキップ可）
python -m backend.scripts.reset_demo_data
🗂️ データモデル
backend/db/models.pyで定義される5テーブル。タイムスタンプ列は全てDateTime型（PR15でSQLite/PostgreSQL両対応のままStringから統一）。以下のER図が示すrequest_id/task_idはSQLAlchemyレベルのForeignKey制約として実際に強制されており（PR15）、robot_tasksには「ロボット単位で非終端状態のタスクは同時に1件まで」という安全制約を守るための部分ユニークインデックス（UNIQUE(robot_id) WHERE state NOT IN ('IDLE','COMPLETED','ERROR')）も張られている。

request_id
task_id
task_id
request_id
task_id
CARE_REQUESTS
string
id
PK
string
patient_id
string
request_type
string
priority
string
status
datetime
created_at
datetime
completed_at
ROBOT_TASKS
string
id
PK
string
request_id
string
robot_id
string
state
string
kit_id
datetime
assigned_at
datetime
updated_at
KIT_VERIFICATIONS
int
id
PK
string
task_id
string
expected_patient_id
string
scanned_patient_id
string
expected_kit_id
string
scanned_kit_id
string
result
text
message
datetime
created_at
TASK_STATE_TRANSITIONS
int
id
PK
string
task_id
string
request_id
string
from_state
string
to_state
string
trigger_type
string
triggered_by
text
reason
datetime
occurred_at
ROBOT_EVENTS
int
id
PK
string
request_id
string
task_id
datetime
timestamp
string
event_type
text
message
care_requests: 患者リクエスト自体（何を・誰が・いつ）。ロボットワークフローの状態は持たない。
robot_tasks: リクエストに対する実際のロボット実行（1タスク=1行、stateがrobot_service.pyのステートマシン値）。ロボット単位（robot_id）で非終端状態（IDLE/COMPLETED以外）のタスクは同時に1件まで、という同時実行制約がある。
kit_verifications: QR照合の試行ごとの1行（OK/NG問わず）。patient_id/kit_idは後方互換のためのエイリアスで、常にscanned_patient_id/scanned_kit_idと同じ値が書き込まれる。expected_*とscanned_*を分けることで、患者違いなのかキット違いなのかをフリーテキストのmessageを読まなくても判別できる（PR9）。
task_state_transitions: robot_tasks.stateが変化するたびの構造化された履歴（PR8）。robot_eventsが人間が読むログなのに対し、こちらはtrigger_type/triggered_byを使って集計しやすくした分析用の記録（/analytics/state-durationsが利用）。
robot_events: 看護師ダッシュボードのログ表示に使う、人間可読なイベントログ。
📊 Analytics API（PR10、PR11）
いずれも認証不要（GET専用、/logsなどの読み取り専用ルートと同じ扱い）。実データの数値を見るには、先に「デモデータ」セクションのseedスクリプトを実行するか、UI/curlで実際にリクエストをいくつか流す。

Method	Path	説明
GET	/analytics/summary	件数系の集計（総リクエスト数・完了/キャンセル数・エラータスク数・QR照合失敗率・平均完了時間）
GET	/analytics/verification-failures	QR照合NGの件数を失敗理由（message）別に集計
GET	/analytics/state-durations	各ロボット状態の平均滞在時間（task_state_transitionsから算出、進行中で未確定の区間は除外）
デモウォークスルー（seed → 起動 → curl）
bash
# 1. バックエンドを起動（別ターミナル）
uvicorn backend.main:app --reload --port 8000

# 2. デモデータを投入（--seedで再現可能な乱数シードを固定できる）
python -m backend.scripts.seed_demo_data --days 7 --tasks 20 --seed 42

# 3. Analytics APIを確認
curl http://localhost:8000/analytics/summary
curl http://localhost:8000/analytics/verification-failures
curl http://localhost:8000/analytics/state-durations
/analytics/summaryのレスポンス例（値は実行のたびに変わる）:

json
{
  "total_requests": 20,
  "completed_requests": 9,
  "cancelled_requests": 4,
  "error_tasks": 2,
  "verification_attempts": 11,
  "verification_failure_rate": 0.1818,
  "average_completion_seconds": 3.4
}
/analytics/verification-failuresのレスポンス例:

json
[
  { "failure_type": "patient_id mismatch", "count": 2 },
  { "failure_type": "kit_id mismatch", "count": 1 }
]
bash
# 4. 使い終わったら削除（確認プロンプトあり、--yesでスキップ）
python -m backend.scripts.reset_demo_data --yes
📈 モニタリング（Grafana、PR16）
docker-compose upすると、/analytics/*と同じ内容をSQLで直接可視化するGrafanaダッシュボードが3枚、手動セットアップなしで最初から使える状態になる（grafana/provisioning/でPostgreSQLデータソースとダッシュボードJSONを自動プロビジョニング）。

ダッシュボード	内容
完了/キャンセル数の推移	care_requestsを日次集計した完了・キャンセル件数の推移
QR照合失敗率	kit_verificationsの全体NG率＋失敗理由（message）別の内訳
状態別平均滞在時間	task_state_transitionsに対するLEAD()ウィンドウ関数で、/analytics/state-durationsと同じロジックをSQLで再現
bash
docker-compose up --build
python -m backend.scripts.seed_demo_data --days 14   # ダッシュボードに表示するデータが要る場合
http://localhost:3000 を開く（admin/adminでログイン、または匿名Viewerアクセスでもダッシュボード閲覧は可能）。

🤖 シミュレーション（Phase 4）
物理ロボットは無いが、ヘッドレスPyBullet(p.DIRECT、画面表示なしでCI/Codespacesでも動く)上でドック位置からベッドサイド位置まで移動する簡易な物理シーンを組み、そこで撮影したフレームを既存のperceptionパイプライン(perception/qr_detector.py)にそのまま流し込んで照合できる。

perception/pybullet_source.pyはperception/camera_source.pyのFrameSourceインターフェース(.frames()でBGRフレームを返す)をそのまま実装しているだけなので、--sourceに渡す文字列を変えるだけで実機Webカメラ・合成動画・PyBulletシミュレーションを切り替えられる。

bash
python -m perception.run_perception \
  --request-id <既存のリクエストID> \
  --source pybullet:delivery_with_qr \
  --base-url http://localhost:8000 \
  --nurse-token $NURSE_TOKEN
QRコードは3D物体へのテクスチャ貼り付けではなく、レンダリング後のフレームに2D画像として合成している（PyBulletのUVマッピング/ライティングに依存させず、cv2.QRCodeDetectorが確実に読み取れる解像度で毎フレーム描画するため）。

配送フロー一括駆動（backend/scripts/run_simulated_delivery.py）
リクエスト作成からQR照合・状態遷移までを、本物のAPI(perception/verification_client.py)越しに一気通貫で実行する開発・デモ用スクリプト。seed_demo_data.pyと同じく、明示的にコマンドを実行したときだけ動く。

bash
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN
安全上の設計: WAITING_FOR_NURSE_CONFIRMATION（キット開放前の看護師確認）に到達すると、このスクリプトは既定ではそこで止まり、人間の確認を待つ。ナースダッシュボードで実際に確認するか、表示されるcurlコマンドを手動で叩く必要がある。--auto-confirmを明示的に付けたときだけスクリプト自身がこのボタンを押すが、これは「有効なナーストークンを持つ誰か/何かがAPIを呼ぶ」という、ダッシュボードが行っているのと全く同じ操作をコマンドラインから行っているだけであり、フラグを付けるという行為自体が人間の意思表示にあたる。tests/test_run_simulated_delivery.pyにはこのゲートが既定では回避されないことを保証する回帰テストがある。

bash
# 看護師確認を自動で行う場合（デモ・CI向け）
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN --auto-confirm
ローカルGUIデモ（backend/scripts/run_gui_demo.py、PR20）
上記は全てヘッドレス（p.DIRECT、画面表示なし）で、CI/Codespacesでも動く。ロボットが実際に動く様子を画面で見たい場合は、ディスプレイのあるローカルマシン限定で以下を実行する（Codespacesでは動かない）。

bash
python -m backend.scripts.run_gui_demo
python -m backend.scripts.run_gui_demo --steps 200 --speed 2.0
PyBulletのGUIウィンドウが開き、ドック位置からベッドサイド位置までロボットが移動する様子を見られる。QRオーバーレイはレンダリング後のフレームへの2D合成であり、ライブのGUIウィンドウには映らない（見た目のデモ専用で、perceptionパイプラインは通らない。QR照合込みの動作確認はrun_simulated_delivery.pyを使う）。

🔌 API エンドポイント
Method	Path	認証	説明
GET	/state	-	現在の状態
GET	/requests	-	リクエスト一覧（現状は最大1件）
POST	/requests	-	患者リクエスト作成
GET	/requests/{id}	-	リクエスト詳細
POST	/requests/{id}/cancel	-	患者キャンセル
POST	/tasks/{id}/transition	🔒	状態遷移
POST	/tasks/{id}/verify	🔒	QR照合
POST	/tasks/{id}/emergency-stop	🔒	緊急停止
POST	/tasks/{id}/reset	🔒	リセット
POST	/tasks/{id}/cancel	🔒	看護師キャンセル
GET	/logs	-	ログ
GET	/analytics/summary	-	件数系の集計
GET	/analytics/verification-failures	-	QR照合失敗の内訳
GET	/analytics/state-durations	-	状態別の平均滞在時間
🔒 = x-nurse-token ヘッダー必須

⚠️ Current Limitations
1ロボットにつき同時にアクティブなタスクは1件まで（robot_id単位。デフォルトロボットは1台のみ運用中）
PostgreSQL/SQLAlchemy永続化（care_requests/robot_tasks/kit_verifications/robot_events/task_state_transitions）。テーブル間の外部キー制約とロボット単位の同時タスク数制約はDBレベルで強制（PR15）
QR照合はダッシュボード上／PyBulletシミュレーション上でシミュレート
物理制御・ナビゲーションは未実装（PyBulletシーン内でも位置を直接設定しているのみ）
Dockerイメージはローカル/デモ用のcomposeスタック向けで、本番デプロイ向けの構成（secrets管理、alembic upgrade headの明示実行など）は別途必要
本プロトタイプは医療機器ではありません
📋 Roadmap
フェーズ	内容	状態
Phase 1–2	API設計・UI分離・ステートマシン	✅
Phase 3	PostgreSQL化・タスクリソースモデル・Perception・合成QRデモ・評価ベンチマーク・CI/品質整備	✅
Phase 3.5	状態遷移履歴・QR照合詳細化・Analytics API・デモデータ・Docker化・README刷新	✅
Phase 4	ヘッドレスPyBulletシミュレーション基盤・QRオーバーレイ・配送フロー一括駆動・DB整合性制約（DateTime/FK/部分ユニークインデックス）・Grafanaダッシュボード・ローカルGUIデモ（pytest 159件）。実カメラ対応／物理制御（ホイール・関節）は未着手	🚧 ほぼ完了
Phase 5	実機MVP・マルチロボット・LeRobot	📋
License
MIT License


