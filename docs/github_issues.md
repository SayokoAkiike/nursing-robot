# GitHub Issues リスト（Day 1〜20）

GitHubの「Issues」タブで以下を1件ずつ作成してください。

---

## Day 1〜6：基盤・UI

**Issue #1 [Day1-2] GitHubリポジトリ初期設定**
- README.md / docs/ / .devcontainer/ をアップロードする
- Codespacesを開いてPythonが動くことを確認
- 完了条件: `pip install -r requirements.txt` が通る

**Issue #2 [Day3-4] 開発環境整備**
- GitHub Codespacesでstreamlitが起動することを確認
- requirements.txtの動作確認
- 完了条件: `streamlit run ui/patient_request_app/app.py` が起動する

**Issue #3 [Day5] 患者リクエストUIの最小版**
- `ui/patient_request_app/app.py` を動かす
- ボタン3つ・待機メッセージ表示を確認
- 完了条件: ボタンを押すと shared_state.json が更新される

**Issue #4 [Day6] 看護師ダッシュボードの最小版**
- `ui/nurse_dashboard/app.py` を動かす
- ロボット状態・リクエスト詳細・ログ表示を確認
- 完了条件: 状態遷移ボタンが動く

---

## Day 7〜11：QR・状態遷移・統合

**Issue #5 [Day7] QRコード生成**
- `python vision/qr_detection/generate_qr.py` を実行
- qr_images/ フォルダに5種類のQR画像が生成される
- 完了条件: QR画像5枚が存在する

**Issue #6 [Day8] QRコード読み取り**
- `python vision/qr_detection/read_qr.py --image <path>` を実行
- 生成したQR画像からIDを読み取れる
- 完了条件: PATIENT_A_ROOM_203 が読み取れる

**Issue #7 [Day9] 患者ID・キットID照合**
- `python vision/qr_detection/verify_patient_kit.py` を実行
- OK/NGの判定が正しく動く
- 完了条件: 5パターンすべて期待通りの結果になる

**Issue #8 [Day10] ロボット状態遷移ダミー**
- `python robot_control/state_machine.py` を実行
- IDLE → COMPLETED まで順番に遷移する
- 完了条件: 動作ログが出力される

**Issue #9 [Day11] UIと状態遷移の統合**
- 患者UIのボタン → shared_state.json → 看護師ダッシュボードの連携確認
- 完了条件: 患者UIのボタン押下が看護師画面に反映される

---

## Day 12〜16：PyBullet・LeRobot設計

**Issue #10 [Day12] GitHub整理・README v1**
- スクリーンショットを撮ってREADMEに追加
- Issue・ラベルを整理する
- 完了条件: READMEにUIのスクリーンショットがある

**Issue #11 [Day13-14] PyBullet入門 + 病室URDF設計**
- `pip install pybullet` で動作確認
- 平面・箱・台車の基本シーンを作る
- 完了条件: PyBulletウィンドウが開く（またはDIRECTモードで動く）

**Issue #12 [Day15-16] 病室シーン構築**
- ベッド・壁・キットステーションをURDFで配置
- 台車ロボットをベッドサイドまで移動させる
- 完了条件: simulation/pybullet_notes/hospital_scene.py が動く

---

## Day 17〜20：評価・まとめ

**Issue #13 [Day17-18] LeRobot調査 + データ設計**
- lerobot/notes/ に調査メモを作成
- 収集するデータ項目を設計する
- 完了条件: lerobot/dataset_design.md が存在する

**Issue #14 [Day19] ドッキング評価指標を定義**
- experiments/docking_metric_plan.md を作成
- 成功判定の数値基準を決める
- 完了条件: 評価指標が5つ以上定義されている

**Issue #15 [Day20] Day20中間まとめ**
- README v2 を更新
- 各成果物のスクリーンショット・動画を整理
- 完了条件: GitHub を見た人がプロジェクトを理解できる

---

## ラベルの作り方

GitHubの Issues → Labels → New label で以下を作成：

| ラベル名 | 色 |
|---------|-----|
| `phase1` | #0075ca |
| `ui` | #7057ff |
| `vision` | #008672 |
| `robot` | #e4e669 |
| `simulation` | #d93f0b |
| `lerobot` | #e99695 |
| `docs` | #cfd3d7 |
