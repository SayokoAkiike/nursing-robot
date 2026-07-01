#  nursing-robot — Bedside Assist Docking Robot (PreCareBot)

> 患者の「トイレに行きたい」リクエストを受け取り、看護師が訪室する前に必要物品キットをベッドサイドへ届けるロボット。

> ⚠️ このプロジェクトは医療機器ではありません。ロボコン・研究・教育目的のプロトタイプです。

---

## 🎯 Problem

病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして転倒するリスクがある。

## 💡 Solution

看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。

---

## 🚧 Safety Boundary

| やること | やらないこと |
|---------|------------|
| 患者リクエストの受信 | 患者の身体を支える |
| キットのベッドサイドへの配送 | 移乗・立たせる |
| QRで患者ID・キットIDを照合 | 点滴・薬剤に触れる |
| 看護師確認後にキットを開放 | 医療判断をする |

詳細 → [docs/safety.md](docs/safety.md)

---

## 現在実装済み

| 機能 | ファイル | 状態 |
|------|---------|------|
| 患者リクエストUI | ui/patient_request_app/app.py | 完了 |
| 看護師ダッシュボード | ui/nurse_dashboard/app.py | 完了 |
| QRコード生成・読み取り・照合 | vision/qr_detection/ | 完了 |
| ロボット状態遷移 | robot_control/state_machine.py | 完了 |
| ログ管理 | robot_control/logger.py | 完了 |
| pytest テスト（9件） | tests/test_core.py | 完了 |

---

## 今後実装予定

| 機能 | フェーズ |
|------|---------|
| PyBullet 病室シミュレーション | Day 13〜18 |
| 実機MVP（台車・トレイ・緊急停止） | Day 21〜40 |
| LeRobotデータセット収集・公開 | Day 41〜55 |
| FastAPI + Next.js UI刷新 | Day 41〜 |

---

## Quick Start

    pip install -r requirements.txt
    python -m streamlit run ui/patient_request_app/app.py --server.port 8501
    python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
    pytest tests/ -v

---

## Roadmap

| フェーズ | 期間 | 内容 | 状態 |
|---------|------|------|------|
| Phase 1 | Day 1〜20 | ソフト基盤・UI・QR・PyBullet入門 | 進行中 |
| Phase 2 | Day 21〜40 | 実機MVP | 予定 |
| Phase 3 | Day 41〜60 | LeRobot・HF公開・模倣学習 | 予定 |

---

## License

MIT License
