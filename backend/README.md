# PreCare Dock — Backend API
 
FastAPIによる薄いAPI層です。Streamlit UIと並行して動作します。
 
## 構成
 
```
backend/
  main.py                    # FastAPI app, router登録, 例外ハンドラ
  api/                        # ルーター（リソース別）
    routes_requests.py
    routes_tasks.py
    routes_verification.py
    routes_logs.py
  core/
    config.py                 # 設定・ドメイン定数（遅延ロード）
    security.py                # 看護師トークン認証
    errors.py                  # 統一エラー型（DomainError系）
  db/
    repositories.py            # 永続化ファサード（現状はJSON、PR2でPostgreSQLに差し替え）
  schemas/                     # Pydanticモデル（用途別）
    request.py / task.py / verification.py / event.py
  services/
    workflow_service.py        # リクエスト作成・状態遷移オーケストレーション
    verification_service.py    # 患者ID・キットID照合ロジック
    robot_service.py            # 状態機械（唯一のルール定義元）
```
 
`robot_control/`・`vision/qr_detection/verify_patient_kit.py` は `ui/` からの参照のために残した後方互換シムです（実体は `backend/` 側）。
 
## 起動方法
 
    uvicorn backend.main:app --reload --port 8000
 
## エンドポイント
 
現状はタスク（`robot_tasks`相当）を1件しか同時に保持できないため、`{request_id}`は404判定にのみ使われます。複数タスクの真の同時実行はPR3（タスクリソースモデル化）で対応予定です。
 
| Method | Path | 認証 | 説明 |
|--------|------|------|------|
| GET | /state | - | 現在の状態を返す |
| GET | /requests | - | リクエスト一覧（現状は最大1件） |
| POST | /requests | - | 患者リクエストを作成する |
| GET | /requests/{request_id} | - | リクエスト詳細 |
| POST | /requests/{request_id}/cancel | - | 患者側キャンセル |
| POST | /tasks/{request_id}/transition | 🔒 | 状態遷移を行う（不正遷移は拒否） |
| POST | /tasks/{request_id}/verify | 🔒 | 患者ID・キットIDを照合する |
| POST | /tasks/{request_id}/emergency-stop | 🔒 | 緊急停止してERRORにする |
| POST | /tasks/{request_id}/reset | 🔒 | IDLEへリセットする |
| POST | /tasks/{request_id}/cancel | 🔒 | 看護師側キャンセル |
| GET | /logs | - | ログ一覧を返す |
 
🔒 = `x-nurse-token` ヘッダー必須
 
## API ドキュメント
 
起動後: http://localhost:8000/docs
 
## 注意
 
このAPIは医療機器ではありません。研究・教育・コンテスト向けのプロトタイプです。
 
