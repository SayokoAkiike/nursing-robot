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
| pytest テスト（38件） | `tests/test_core.py` | ✅ |

## ❌ 未実装（今後の予定）

| 機能 | 予定フェーズ |
|------|------------|
| SQLite / DB移行（現在: JSONファイル） | Phase 3 |
| PyBullet 病室シミュレーション | Phase 3 |
| カメラQRリアルタイムスキャン | Phase 3 |
| 複数同時リクエスト対応 | Phase 3 |
| 物理ロボット制御・ナビゲーション | Phase 4 |
| マルチロボット・複数病棟対応 | Phase 5 |

---

## 🏗️ アーキテクチャPatient UI (port 8501)      Nurse Dashboard (port 8502)
↓ HTTP                         ↓ HTTP
ui/common/api_client.py
↓
FastAPI Backend (port 8000)
backend/main.py
↓
Service Layer
robot_control/service.py
↓
Storage (JSON → Phase 3 で SQLite へ)
shared_state.json / robot_log.json
**設計方針**: UI → HTTP → API → Service → Storage の分離により、将来の複数患者・複数ロボット・DBへの移行に対応しやすくしています。

---

## 🔄 ステートマシン（10ステップ）IDLE → REQUEST_RECEIVED → KIT_SELECTED → MOVING_TO_BEDSIDE
→ VERIFYING_PATIENT (POST /tasks/{id}/verify でQR照合)
→ DOCKING → TRAY_LIFTING
→ WAITING_FOR_NURSE_CONFIRMATION
→ KIT_RELEASED → COMPLETEDどの状態からも ERROR へ遷移可能（緊急停止時）。COMPLETED / ERROR からは reset で IDLE へ。

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v
```

---

## 🔌 API エンドポイント

| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| GET | `/requests` | - | リクエスト一覧 |
| POST | `/requests` | - | 患者リクエスト作成 |
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

- シングルリクエスト制約（同時1件のみ）
- JSON ファイルストレージ（並列アクセス非対応、Phase 3 で SQLite 予定）
- QR照合はダッシュボード上でシミュレート
- 物理制御・ナビゲーションは未実装
- 本プロトタイプは医療機器ではありません

---

## 📋 Roadmap

| フェーズ | 内容 | 状態 |
|---------|------|------|
| Phase 1–2 | API設計・UI分離・ステートマシン・pytest 38件 | ✅ |
| Phase 3 | SQLite移行・複数リクエスト・CI整備 | 🔨 |
| Phase 4 | PyBullet シミュレーション | 📋 |
| Phase 5 | 実機MVP・LeRobot | 📋 |

---

## License

MIT License
