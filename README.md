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
| サービス層 | `robot_control/service.py` | ✅ |
| QRコード生成・照合 | `vision/qr_detection/` | ✅ |
| イベントログ | `robot_control/logger.py` | ✅ |
| PostgreSQL/SQLAlchemy永続化 + Alembicマイグレーション | `backend/db/`, `alembic/` | ✅ |
| タスクリソースモデル（care_requests/robot_tasks/kit_verifications、ロボット単位の同時実行制約） | `backend/db/models.py`, `backend/services/workflow_service.py` | ✅ |
| Perceptionモジュール（複数フレーム確定QR検出＋照合APIクライアント） | `perception/` | ✅ |
| 合成QRデモ動画生成（実写映像不使用） | `vision/qr_detection/demo/` | ✅ |
| QR検出の評価ベンチマーク（confirm_frames毎の検出成功率・所要フレーム数・不安定検出数） | `perception/evaluate_detector.py` | ✅ |
| 品質管理（ruff / mypy / pytest-cov / CI） | `ruff.toml`, `mypy.ini`, `.coveragerc`, `.github/workflows/pytest.yml` | ✅ |
| pytest テスト（89件） | `tests/` （API/workflow service/state machine/repositories/verification/perception/vision） | ✅ |
 
## ❌ 未実装（今後の予定）
 
| 機能 | 予定フェーズ |
|------|------------|
| PyBullet 病室シミュレーション | Phase 4 |
| 実カメラでのリアルタイムQRスキャン（現状は合成動画/画像ディレクトリ入力のみ検証済み） | Phase 4 |
| 物理ロボット制御・ナビゲーション | Phase 4 |
| マルチロボット・複数病棟対応 | Phase 5 |


## 🚀 Quick Start
 
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v
```

### 品質チェック（PR7）

```bash
ruff check .
mypy backend perception vision
pytest tests/ --cov=backend --cov=perception --cov=vision --cov-report=term-missing
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
 
🔒 = x-nurse-token ヘッダー必須
 
---
 
## ⚠️ Current Limitations
 
- 1ロボットにつき同時にアクティブなタスクは1件まで（`robot_id`単位。デフォルトロボットは1台のみ運用中）
- PostgreSQL/SQLAlchemy永続化（`care_requests`/`robot_tasks`/`kit_verifications`/`robot_events`）
- QR照合はダッシュボード上でシミュレート
- 物理制御・ナビゲーションは未実装
- 本プロトタイプは医療機器ではありません
 
---
 
## 📋 Roadmap
 
| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1–2 | API設計・UI分離・ステートマシン | ✅ |
| Phase 3 | PostgreSQL化・タスクリソースモデル・Perception・合成QRデモ・評価ベンチマーク・CI/品質整備（pytest 89件） | ✅ |
| Phase 4 | PyBulletシミュレーション・実カメラ対応 | 📋 |
| Phase 5 | 実機MVP・LeRobot | 📋 |
 
---
 
## License
 
MIT License
 
 

