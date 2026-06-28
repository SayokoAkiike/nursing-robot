# 🏥 nursing-robot — Bedside Assist Docking Robot (PreCareBot)

> **患者の「トイレに行きたい」リクエストを受け取り、看護師が訪室する前にトイレ介助キットをベッドサイドへ届けるラストワンマイルロボット。**

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red)](https://streamlit.io)
[![PyBullet](https://img.shields.io/badge/Sim-PyBullet-orange)](https://pybullet.org)
[![HuggingFace](https://img.shields.io/badge/Data-HuggingFace-yellow)](https://huggingface.co)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🎯 Problem（解決したい問題）

病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして**転倒するリスク**がある。特に夜間・人手不足の時間帯に起きやすい。

## 💡 Solution（解決策）

看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。

```
患者がボタンを押す
       ↓
ロボットがキットを選択・ベッドサイドへ移動
       ↓
QRコードで患者IDを照合
       ↓
トレイを看護師が使いやすい高さに提示
       ↓
患者画面：「立ち上がらずお待ちください」
       ↓
看護師が確認ボタン → キット開放 → ログ記録
```

---

## 🚧 Safety Boundary（安全境界）

| ✅ やること | ❌ やらないこと |
|-----------|--------------|
| 患者リクエストの受信 | 患者の身体を支える |
| キットのベッドサイドへの配送 | 移乗・立たせる |
| QRで患者ID・キットIDを照合 | 点滴・薬剤に触れる |
| 看護師確認後にキットを開放 | 医療判断をする |
| 患者への待機メッセージ表示 | 看護師確認なしに開放 |

> 詳細 → [docs/safety.md](docs/safety.md)

---

## 🏗 System Architecture

```
┌──────────────┐  request   ┌──────────────┐  state   ┌──────────────┐
│  Patient UI  │──────────▶│ Task Router  │─────────▶│   Nurse      │
│ (Streamlit)  │            │  (Python)    │           │  Dashboard   │
└──────────────┘            └──────┬───────┘           │ (Streamlit)  │
                                   │                   └──────────────┘
                        ┌──────────▼───────┐
┌──────────────┐  QR   │  State Machine   │
│ OpenCV/QR    │───────▶│ (robot_control)  │
│ (ArUco対応)  │        └──────────────────┘
└──────────────┘
        ↕ Sim-to-Real 検証
┌──────────────┐
│  PyBullet    │  ← Isaac Simの代替（CPU動作・完全無料）
│  病室シミュ  │
└──────────────┘
```

---

## 🛠 Tech Stack

| 技術 | 用途 | 無料？ |
|------|------|--------|
| Python 3.10+ | メイン制御・状態管理 | ✅ |
| Streamlit | 患者UI・看護師ダッシュボード | ✅ |
| OpenCV | QR/ArUco認識・ID照合 | ✅ |
| PyBullet | 病室シミュレーション（CPU動作） | ✅ |
| Hugging Face / LeRobot | データセット公開・模倣学習 | ✅ パブリック無制限 |
| GitHub Codespaces | 開発環境（ブラウザで動く） | ✅ 月60h無料 |
| Google Colab | 模倣学習実験（無料GPU） | ✅ |

---

## 📁 Repository Structure

```
nursing-robot/
├── README.md
├── requirements.txt
├── .devcontainer/
│   └── devcontainer.json        # Codespaces設定（pip自動実行）
├── docs/
│   ├── concept.md               # プロジェクトコンセプト
│   ├── safety.md                # 安全境界の定義
│   ├── demo_scenario.md         # 1分デモ台本
│   └── roadmap.md               # Day別ロードマップ
├── ui/
│   ├── patient_request_app/
│   │   └── app.py               # 患者リクエスト画面
│   └── nurse_dashboard/
│       └── app.py               # 看護師ダッシュボード
├── vision/
│   └── qr_detection/
│       ├── generate_qr.py       # QRコード生成
│       ├── read_qr.py           # QRコード読み取り
│       └── verify_patient_kit.py # 患者ID・キットID照合
├── robot_control/
│   ├── state_machine.py         # ロボット状態遷移
│   ├── task_router.py           # リクエスト振り分け
│   └── dummy_robot.py           # 実機なしダミー動作
├── simulation/
│   └── pybullet_notes/
│       ├── what_is_pybullet.md  # PyBullet調査メモ
│       └── hospital_scene.py    # 病室シーン（Day13〜）
├── lerobot/
│   ├── notes/
│   │   └── dataset_card_draft.md
│   └── dataset_design.md
├── hardware/
│   ├── parts_list.md            # 実機MVP部品リスト
│   └── wiring_plan.md
└── experiments/
    └── docking_metric_plan.md   # ドッキング評価指標
```

---

## 🚀 Quick Start（GitHub Codespaces）

**ブラウザだけで動かす方法：**

1. このページ右上の「Code」→「Codespaces」→「Create codespace」をクリック
2. ターミナルが開いたら以下を実行：

```bash
# 依存関係インストール（自動で実行される場合もある）
pip install -r requirements.txt

# 患者UI起動
streamlit run ui/patient_request_app/app.py --server.port 8501

# 別ターミナルで看護師ダッシュボード起動
streamlit run ui/nurse_dashboard/app.py --server.port 8502
```

---

## 🗓 Roadmap

| フェーズ | 期間 | 内容 |
|---------|------|------|
| **Phase 1** | Day 1〜20 | GitHub整備・UI・QR照合・PyBullet入門・LeRobot設計 |
| **Phase 2** | Day 21〜40 | 実機MVP（台車・トレイ・緊急停止・デモ動画） |
| **Phase 3** | Day 41〜60 | テレオペデータ収集・HF公開・模倣学習実験 |

> 詳細 → [docs/roadmap.md](docs/roadmap.md)

---

## 👥 Team

| 名前 | 役割 |
|------|------|
| Sayoko Akiike | プロジェクトリード |
| （メンバー追加予定） | — |

---

## 📄 License

MIT License — 詳細は [LICENSE](LICENSE) を参照

---

*このプロジェクトは医療機器ではありません。ロボコン・研究・教育目的のプロトタイプです。*
