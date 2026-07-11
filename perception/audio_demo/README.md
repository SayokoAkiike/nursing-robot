# デモ用音声ファイル（PR29）

`toileting_ja.wav` は `espeak-ng`（オフラインのルールベースTTS）で機械合成した
「トイレに行きたいです」の音声です。実在の人物の声・患者の音声は一切含まれて
いません（生成コマンドは下記）。

```bash
espeak-ng -v ja -s 140 "トイレに行きたいです" -w perception/audio_demo/toileting_ja.wav
```

`espeak-ng`の日本語合成は機械的でイントネーションが乏しいため、
faster-whisperでの書き起こし精度は人間の自然発話ほど高くない可能性があります。
動作確認（配管が正しくつながっているかの確認）が主目的で、認識精度のベンチ
マークではありません。より自然な音声で試したい場合は、自分の声を録音した
WAVファイルを`--audio-file`に渡してください。

```bash
python -m backend.scripts.run_simulated_rounding \
  --scenario rounding_toileting_escalation \
  --nurse-token $NURSE_TOKEN \
  --audio-file perception/audio_demo/toileting_ja.wav
```
