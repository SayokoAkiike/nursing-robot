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
    session.py                  # SQLAlchemyエンジン/セッション（DATABASE_URL未設定ならSQLiteにフォールバック）
    models.py                   # ORMモデル（care_requests, robot_events）
    repositories.py             # 永続化ファサード（PR2よりSQLAlchemy経由でDB化）
  schemas/                     # Pydanticモデル（用途別）
    request.py / task.py / verification.py / event.py
  services/
    workflow_service.py        # リクエスト作成・状態遷移オーケストレーション
    verification_service.py    # 患者ID・キットID照合ロジック
    robot_service.py            # 状態機械（唯一のルール定義元）
```
 
`robot_control/`・`vision/qr_detection/verify_patient_kit.py` は `ui/` からの参照のために残した後方互換シムです（実体は `backend/` 側）。
 
## タスクリソースモデル（PR3）

`request_id`は実在する`care_requests`行を指し、`robot_tasks`行と結合されます。以前（PR1/PR2）は単一のシングルトン行しか存在せず、`request_id`は404判定にしか使われていませんでしたが、現在は本当に複数の`care_requests`/`robot_tasks`が存在できます。

- 同時実行制約: 1ロボット（`robot_id`）につきアクティブな`robot_tasks`は1件まで（`backend/services/workflow_service.py`の`create_request`）。制約はロボット単位なので、将来ロボットが増えてもスキーマ変更なしで並行実行できます。
- キャンセル・リセット後も`request_id`で履歴を参照可能（旧JSON方式は全消去していました）。
- QR照合は`kit_verifications`に成功・失敗を問わず1件ずつ記録されます（`robot_events`とは別の監査ログ）。


## データベース
 
デフォルトはSQLite（`data/precare.db`、設定不要）。PostgreSQLを使う場合:
 
```bash
docker-compose up -d
cp .env.example .env  # DATABASE_URLのコメントを外す
alembic upgrade head
```
 
テストは常にテストごとに独立したSQLiteファイルを使います（`tests/conftest.py`の`robot_storage`フィクスチャ）。CIでPostgreSQLコンテナを起動する必要はありません。
 
スキーマ変更はAlembicで管理します:
 
```bash
alembic revision --autogenerate -m "変更内容"
alembic upgrade head
```
 
 
## 起動方法
 
    uvicorn backend.main:app --reload --port 8000
 
## エンドポイント
 
`{request_id}`は`care_requests`行を実際に指します（詳細は上記「タスクリソースモデル」参照）。
 
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
 
 

