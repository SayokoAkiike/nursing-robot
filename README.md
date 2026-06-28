🏥 nursing-robot — Bedside Assist Docking Robot (PreCareBot)

患者の「トイレに行きたい」リクエストを受け取り、看護師が訪室する前にキットをベッドサイドへ届けるラストワンマイルロボット。
⚠️ このプロジェクトは医療機器ではありません。ロボコン・研究・教育目的のプロトタイプです。


🎯 Problem
病院でナースコールから看護師到着まで数分かかる間に、患者が一人で立ち上がろうとして転倒するリスクがある。
💡 Solution
看護師が訪室するより先にロボットがキットを届け、患者画面に「立ち上がらずお待ちください」と表示する。

🚧 Safety Boundary（安全境界）
✅ やること❌ やらないこと患者リクエストの受信患者の身体を支えるキットのベッドサイドへの配送移乗・立たせるQRで患者ID・キットIDを照合点滴・薬剤に触れる看護師確認後にキットを開放医療判断をする患者への待機メッセージ表示看護師確認なしに開放
詳細 → docs/safety.md

✅ 現在実装済み・デモで動くもの
機能ファイル状態患者リクエストUIui/patient_request_app/app.py✅看護師ダッシュボードui/nurse_dashboard/app.py✅QRコード生成vision/qr_detection/generate_qr.py✅QRコード読み取りvision/qr_detection/read_qr.py✅患者ID・キットID照合vision/qr_detection/verify_patient_kit.py✅ロボット状態遷移（ダミー）robot_control/state_machine.py✅ログ管理robot_control/logger.py✅pytest テスト（9件）tests/test_core.py✅

🔜 今後実装予定
機能フェーズPyBullet 病室シミュレーションDay 13〜18実機MVP（台車・トレイ・緊急停止）Day 21〜40LeRobotデータセット収集・公開Day 41〜55Google Colab 模倣学習実験Day 56〜60FastAPI + Next.js UI刷新Day 41〜

🛠 Tech Stack
技術用途状態Python 3.10+メイン制御・状態管理✅ 実装済みStreamlit患者UI・看護師ダッシュボード✅ 実装済みOpenCVQR/ArUco認識・ID照合✅ 実装済みpytestテスト（9件）✅ 実装済みPyBullet病室シミュレーション（CPU動作）🔜 Day13〜Hugging Face / LeRobotデータセット公開・模倣学習🔜 Day41〜FastAPI + Next.jsUI刷新・API化🔜 Day41〜

🚀 Quick Start
pip install -r requirements.txt
python vision/qr_detection/generate_qr.py
python -m streamlit run ui/patient_request_app/app.py --server.port 8501
python -m streamlit run ui/nurse_dashboard/app.py --server.port 8502
pytest tests/ -v

🗓 Roadmap
フェーズ期間内容状態Phase 1Day 1〜20ソフト基盤・UI・QR・PyBullet入門🔥 進行中Phase 2Day 21〜40実機MVP（台車・トレイ・緊急停止）🔜 予定Phase 3Day 41〜60LeRobot・HF公開・模倣学習実験🔜 予定

📊 進捗（2026-06-28時点）
Day内容状態Day 1〜4GitHub・Codespaces環境構築✅Day 5患者リクエストUI✅Day 6看護師ダッシュボード✅Day 7QRコード生成✅Day 8QRコード読み取り✅Day 9患者ID・キットID照合✅Day 10ロボット状態遷移ダミー実装✅Day 11UIと状態遷移の統合・自動更新✅Day 12GitHub整理・README更新✅Day 13〜PyBullet病室シミュ🔜

👥 Team
名前役割Sayoko Akiikeプロジェクトリード

📄 License
MIT License
