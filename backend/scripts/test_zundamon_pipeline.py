"""ZundamonPipelineBackend の配線確認用スクリプト。
マイク入力の代わりに、VOICEVOXで「テスト用の患者発話」を音声合成し、
それをそのままWhisper→Gemini→VOICEVOXのパイプラインに通して、
最初から最後まで壊れていないかを確認する。
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT_DIR / ".env")

import requests  # noqa: E402
from backend.services.voice_backends import get_backend  # noqa: E402

VOICEVOX_BASE_URL = "http://localhost:50021"
TEST_PHRASE = "トイレに行きたいです"
TEST_SPEAKER_ID = 3  # ずんだもん(ノーマル) -- 患者役の声としてはとりあえず流用


def synthesize_test_audio(text: str) -> bytes:
    """患者発話の代役として、VOICEVOXでテスト音声を作る。"""
    query = requests.post(
        f"{VOICEVOX_BASE_URL}/audio_query",
        params={"text": text, "speaker": TEST_SPEAKER_ID},
    ).json()
    audio = requests.post(
        f"{VOICEVOX_BASE_URL}/synthesis",
        params={"speaker": TEST_SPEAKER_ID},
        json=query,
    )
    return audio.content


def main():
    print(f"[1/3] テスト用患者発話を音声合成中: 「{TEST_PHRASE}」")
    test_audio = synthesize_test_audio(TEST_PHRASE)
    print(f"      -> {len(test_audio)} bytes の音声を生成")

    print("[2/3] ZundamonPipelineBackend を初期化中（Whisperモデル読み込み含む、少し時間がかかります）")
    backend = get_backend("ずんだもん")

    print("[3/3] パイプライン実行中（STT -> LLM -> TTS）")
    result = backend.respond(test_audio)

    print("\n===== 結果 =====")
    print(f"認識されたテキスト（Whisper）: {result.transcript}")
    print(f"ロボットの応答テキスト（Gemini）: {result.response_text}")
    print(f"応答音声のサイズ: {len(result.response_audio)} bytes")

    out_path = ROOT_DIR / "backend" / "scripts" / "test_output.wav"
    out_path.write_bytes(result.response_audio)
    print(f"\n応答音声を保存しました: {out_path}")


if __name__ == "__main__":
    main()
