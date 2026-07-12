# 機能詳細

[README](../README.md)の続き。Analytics API・Grafana・シミュレーションスクリプト・要望分類の仕組み・異常検知の、詳しい使い方と設計判断をまとめている。

- [Analytics API](#analytics-api)
- [Grafana](#grafana)
- [シミュレーションスクリプト](#シミュレーション)
- [要望分類の3段構え](#要望分類の3段構えキーワード--埋め込み--ローカルllm)
- [エスカレーションパターンの異常検知](#エスカレーションパターンの異常検知)
- [ローカルGUIデモ](#ローカルguiデモ)

---

## Analytics API

いずれも認証不要（GET専用、`/logs`などの読み取り専用ルートと同じ扱い）。実データの数値を見るには、先にデモデータのseedスクリプトを実行するか、UI/curlで実際にリクエストをいくつか流す。

| Method | Path | 説明 |
|--------|------|------|
| GET | `/analytics/summary` | 件数系の集計（総リクエスト数・完了/キャンセル数・エラータスク数・QR照合失敗率・平均完了時間） |
| GET | `/analytics/verification-failures` | QR照合NGの件数を失敗理由（`message`）別に集計 |
| GET | `/analytics/state-durations` | 各ロボット状態の平均滞在時間（`task_state_transitions`から算出、進行中で未確定の区間は除外） |
| GET | `/analytics/rounding-summary` | 巡回セッション数・患者発見数・要望分類数・エスカレーション数・URGENT件数・平均ack時間 |
| GET | `/analytics/escalation-breakdown` | `nurse_escalations`をpriority別/detected_need別/status別に集計 |
| GET | `/analytics/escalation-anomalies` | 患者ごとのエスカレーションパターンの教師なし異常検知（詳細は下記） |

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

<details>
<summary>各エンドポイントのレスポンス例</summary>

`/analytics/summary`（値は実行のたびに変わる）:

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

`/analytics/verification-failures`:

```json
[
  { "failure_type": "patient_id mismatch", "count": 2 },
  { "failure_type": "kit_id mismatch", "count": 1 }
]
```

`/analytics/rounding-summary`:

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

`/analytics/escalation-breakdown`:

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

</details>

```bash
# 4. 使い終わったら削除（確認プロンプトあり、--yesでスキップ）
python -m backend.scripts.reset_demo_data --yes
```

---

## Grafana

`docker-compose up`すると、`/analytics/*`と同じ内容をSQLで直接可視化するGrafanaダッシュボードが5枚、手動セットアップなしで最初から使える状態になる（`grafana/provisioning/`でPostgreSQLデータソースとダッシュボードJSONを自動プロビジョニング）。

| ダッシュボード | 内容 |
|---------------|------|
| 完了/キャンセル数の推移 | `care_requests`を日次集計した完了・キャンセル件数の推移 |
| QR照合失敗率 | `kit_verifications`の全体NG率＋失敗理由（`message`）別の内訳 |
| 状態別平均滞在時間 | `task_state_transitions`に対する`LEAD()`ウィンドウ関数で、`/analytics/state-durations`と同じロジックをSQLで再現 |
| 巡回セッション概況 | 巡回セッション数・患者発見数・要望分類数・エスカレーション数・URGENT件数・平均ack時間、日次セッション数の推移 |
| エスカレーションキュー | 未確認(PENDING)件数・平均ack時間、priority別/need別の内訳（円グラフ）、status別件数（テーブル） |

```bash
docker-compose up --build
python -m backend.scripts.seed_demo_data --days 14   # ダッシュボードに表示するデータが要る場合
```

`http://localhost:3000` を開く（admin/adminでログイン、または匿名Viewerアクセスでもダッシュボード閲覧は可能）。

---

## シミュレーション

物理ロボットは無いが、ヘッドレスPyBullet（`p.DIRECT`、画面表示なしでCI/Codespacesでも動く）上でドック位置からベッドサイド位置まで移動する簡易な物理シーンを組み、そこで撮影したフレームを既存のperceptionパイプライン（`perception/qr_detector.py`）にそのまま流し込んで照合できる。

`perception/pybullet_source.py`は`perception/camera_source.py`の`FrameSource`インターフェース（`.frames()`でBGRフレームを返す）をそのまま実装しているだけなので、`--source`に渡す文字列を変えるだけで実機Webカメラ・合成動画・PyBulletシミュレーションを切り替えられる。

```bash
python -m perception.run_perception \
  --request-id <既存のリクエストID> \
  --source pybullet:delivery_with_qr \
  --base-url http://localhost:8000 \
  --nurse-token $NURSE_TOKEN
```

QRコードは3D物体へのテクスチャ貼り付けではなく、レンダリング後のフレームに2D画像として合成している（PyBulletのUVマッピング/ライティングに依存させず、`cv2.QRCodeDetector`が確実に読み取れる解像度で毎フレーム描画するため）。

### 配送フロー一括駆動（`run_simulated_delivery.py`）

リクエスト作成からQR照合・状態遷移までを、本物のAPI（`perception/verification_client.py`）越しに一気通貫で実行する開発・デモ用スクリプト。

```bash
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN
```

**安全上の設計**: `WAITING_FOR_NURSE_CONFIRMATION`（キット開放前の看護師確認）に到達すると、既定では**そこで止まり、人間の確認を待つ**。`--auto-confirm`を明示的に付けたときだけスクリプト自身がこのボタンを押す（有効なナーストークンを持つ何かがAPIを呼ぶという、ダッシュボードと同じ操作をコマンドラインから行っているだけ）。

```bash
python -m backend.scripts.run_simulated_delivery --nurse-token $NURSE_TOKEN --auto-confirm
```

### 巡回・見守りワークフロー一括駆動（`run_simulated_rounding.py`）

7つの名前付きシナリオ（`rounding_normal` / `rounding_patient_detected` / `rounding_toileting_escalation` / `rounding_water_request` / `rounding_no_need` / `rounding_urgent_pain` / `rounding_fall_risk`）それぞれに紐づく疑似患者応答を、本物のAPI（`/rounding/*`、`/escalations/*`）越しに流す。分類結果を期待値と照合するので、`need_classification_service`のE2Eスモークテストも兼ねる。

```bash
python -m backend.scripts.run_simulated_rounding --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN --auto-ack
```

`run_simulated_delivery.py`と同じ思想で、エスカレーションが発生するシナリオは既定では`WAITING_FOR_NURSE_ACK`で止まる。`INFORMATION_ONLY`ルートはそもそも看護師ゲートが無いので常に`COMPLETED`まで進む。

### 実音声認識（`--audio-file`）

`run_simulated_rounding.py`に`--audio-file`を渡すと、シナリオの疑似応答テキストの代わりに、指定したWAVファイルを実際に音声認識（[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、CPU/int8、完全オフライン）した結果を`/classify-need`に流す。クラウドAPIには一切送信しない。

```bash
python -m backend.scripts.run_simulated_rounding \
  --scenario rounding_toileting_escalation --nurse-token $NURSE_TOKEN \
  --audio-file perception/audio_demo/toileting_ja.wav --auto-ack
```

デフォルトモデルは`medium`（精度重視、初回ダウンロード約1.5GB）＋VAD（無音区間の除去）。ディスク容量やダウンロード時間が厳しい環境では`SPEECH_MODEL_SIZE=small`（約470MB）に切り替えられる。`perception/audio_demo/toileting_ja.wav`は`espeak-ng`合成音声（実在の人物の声は含まれない、詳細は同ディレクトリの`README.md`）。

### 実姿勢推定・離床検知（`run_pose_demo.py`）

[MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker)で骨格を推定し、腰のランドマークがベッド領域の外に出たら離床（`fall_risk`）と判定する監視ループ。位置判定だけでなく、腰の**速度・加速度**もフレームごとに追跡している（`MotionTracker`）。ベッド境界をまたぐ瞬間は1フレームに収まらないことがあり、静止位置だけでは転倒の瞬間を見逃す場合があるため、急な下方向の動きも独立した`fall_risk`シグナルとして扱う。

`--confirm-frames`（既定5）フレーム連続で判定されて初めて`POST /escalations/vision-report`（`x-robot-token`必須）でエスカレーションする。映像・画像はどこにも保存しない。

```bash
python -m backend.scripts.download_pose_model  # 初回のみ

python -m backend.scripts.run_pose_demo \
  --source webcam:0 --room 203 --patient-id PATIENT_A_ROOM_203 \
  --bed-region 0.2,0.5,0.8,1.0 --base-url http://localhost:8000 --robot-token $ROBOT_TOKEN
```

Webカメラはローカルマシン限定（Codespacesにはカメラがない）。静止画ディレクトリで代用する場合：

```bash
mkdir -p /tmp/test_frames
python3 -c "
import cv2, numpy as np
cv2.imwrite('/tmp/test_frames/frame_001.png', np.zeros((480,640,3), dtype=np.uint8))
"
python -m backend.scripts.run_pose_demo --source /tmp/test_frames --room 203 --patient-id PATIENT_A_ROOM_203 --bed-region 0.2,0.5,0.8,1.0 --confirm-frames 1 --robot-token $ROBOT_TOKEN
```

姿勢推定を使うにはOSレベルの共有ライブラリが2つ追加で必要（Codespacesの標準イメージには入っていない）:

```bash
sudo apt-get update && sudo apt-get install -y libgles2 libegl1
```

---

## 要望分類の3段構え（キーワード → 埋め込み → ローカルLLM）

`rounding_service.classify_need()`の要望分類は、3段階のフォールバックチェーンになっている。

1. **キーワードマッチ**（`need_classification_service.py`）：高速・決定的・追加依存なし
2. **文埋め込み類似度**（`semantic_classification_service.py`）：キーワードに一致しなかった場合のみ、言い換え表現を拾う
3. **ローカルLLM**（`llm_classification_service.py`）：前の2段階が両方とも`unknown`だった場合のみ、[LiquidAI/LFM2.5-1.2B-JP-GGUF](https://huggingface.co/LiquidAI/LFM2.5-1.2B-JP-GGUF)（日本語特化・約730MB・Q4量子化）に分類させる

各段階は前段階が`unknown`のときだけ呼ばれ、後の段階が前段階の確信度の高い答えを上書きすることはない。3段階とも失敗しても`classify_need()`自体は失敗せず、キーワード段階の結果にそのまま倒れる——安全性は、精度向上の追加機能が使えるかどうかに依存しない。

`llama-cpp-python`は`torch`に依存しない軽量なバインディングだが、PyPIにプリビルドwheelが無く、`pip install`のたびにC++バックエンドをソースからビルドする（数分かかることがあるが、フリーズしているわけではない）。

### レイテンシの実測

```bash
# 各段階のモデルを一度ダウンロード済みの状態で実行すること
python -m backend.scripts.benchmark_classification_chain

# llama-cpp-pythonが未ビルドの環境ではLLM段階だけ飛ばせる
python -m backend.scripts.benchmark_classification_chain --skip-llm
```

キーワード段階・埋め込み段階（初回ロード＋定常状態）・LLM段階（同）・3段階フル通過の合計時間をミリ秒単位で表示する。このスクリプトは3つのHugging Faceリポジトリに一度にアクセスするため、`HF_TOKEN`未設定だと`429 Too Many Requests`にぶつかりやすい（[README](../README.md)のセットアップチェックリスト参照）。

---

## エスカレーションパターンの異常検知

当初「将来の転倒リスクを予測するスコアリング」として構想されていた機能だが、それには実際の転倒（アウトカム）の正解ラベルが必要で、合成デモデータしか無いこのプロトタイプでは原理的に作れない（合成データ生成に使ったルール自体をノイズ付きで再学習するだけになる）。そのため、ラベル不要の**教師なし異常検知**として実装している：「この患者の直近のエスカレーションパターンは、他の患者と比べて統計的に外れているか」を`scikit-learn`の`IsolationForest`で判定する（患者ごとのエスカレーション件数・URGENT件数の割合・平均優先度・平均ack時間を特徴量として使用、フィッティング前に`StandardScaler`で標準化）。

比較対象の患者数が少なすぎると統計的な意味を持たないため、5人未満のデータしか無い場合は空の結果を返す（無理に数値を出さない）。

```bash
curl http://localhost:8000/analytics/escalation-anomalies
```

---

## ローカルGUIデモ

上記は全てヘッドレス（`p.DIRECT`、画面表示なし）で、CI/Codespacesでも動く。ロボットが実際に動く様子を画面で見たい場合は、ディスプレイのあるローカルマシン限定で以下を実行する（**Codespacesでは動かない**）。

```bash
python -m backend.scripts.run_gui_demo
python -m backend.scripts.run_gui_demo --steps 200 --speed 2.0
```

PyBulletのGUIウィンドウが開き、ドック位置からベッドサイド位置までロボットが移動する様子を見られる。QRオーバーレイはレンダリング後のフレームへの2D合成であり、ライブのGUIウィンドウには映らない（見た目のデモ専用。QR照合込みの動作確認は`run_simulated_delivery.py`を使う）。
