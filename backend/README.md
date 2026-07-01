# PreCare Dock — Backend API

FastAPIによる薄いAPI層です。Streamlit UIと並行して動作します。

## 起動方法

    uvicorn backend.main:app --reload --port 8000

## エンドポイント

| Method | Path | 説明 |
|--------|------|------|
| GET | /state | 現在の状態を返す |
| POST | /requests | 患者リクエストを作成する |
| POST | /transition | 状態遷移を行う（不正遷移は拒否） |
| POST | /verify | 患者ID・キットIDを照合する |
| POST | /emergency-stop | 緊急停止してERRORにする |
| POST | /reset | IDLEへリセットする |
| GET | /logs | ログ一覧を返す |

## API ドキュメント

起動後: http://localhost:8000/docs

## 注意

このAPIは医療機器ではありません。研究・教育・コンテスト向けのプロトタイプです。
