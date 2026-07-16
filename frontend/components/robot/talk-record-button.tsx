"use client";

import { useHover } from "@/hooks/use-hover";
import { useVoiceRecorder, type VoiceEngine, type VoiceTurnResult } from "@/hooks/use-voice-recorder";

/**
 * The robot screen's single "話しかける" button: tap to start recording,
 * tap again to stop and send the recording to whichever voice engine is
 * selected (backend/services/voice_backends/), replacing what used to be
 * two separate controls (a canned demo-scenario button and a standalone
 * mic-recording panel).
 */
export function TalkRecordButton({
  onResult,
  disabled = false,
  disabledLabel = "巡回・要望分類を実行中…",
}: {
  onResult: (result: VoiceTurnResult) => void;
  disabled?: boolean;
  disabledLabel?: string;
}) {
  const { engine, setEngine, status, processingLabel, errorMessage, toggleRecording } =
    useVoiceRecorder(onResult);
  const { hover, hoverHandlers } = useHover();

  const busy = status === "processing" || disabled;
  const canRun = !busy && status !== "recording";

  const label =
    status === "recording"
      ? "録音中… タップで終了"
      : status === "processing"
        ? processingLabel
        : disabled
          ? disabledLabel
          : "話しかける";

  return (
    <div className="flex flex-col gap-3">
      <select
        value={engine}
        onChange={(e) => setEngine(e.target.value as VoiceEngine)}
        disabled={status === "recording" || busy}
        className="w-full shrink-0 rounded-[8px] border bg-white px-2.5 py-[7px] text-[12.5px]"
        style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.4 0.015 250)" }}
      >
        <option value="ずんだもん">音声エンジン: ずんだもん</option>
        <option value="Gemini Live">音声エンジン: Gemini Live</option>
      </select>

      <button
        type="button"
        onClick={toggleRecording}
        disabled={busy}
        {...hoverHandlers}
        className="box-border flex w-full items-center justify-center gap-3 rounded-full border-none py-[26px] text-[19px] font-bold transition-transform duration-150"
        style={{
          cursor: busy ? "not-allowed" : "pointer",
          background:
            status === "recording"
              ? "oklch(0.55 0.19 25)"
              : busy
                ? "oklch(0.9 0.003 260)"
                : "oklch(0.4 0.19 265)",
          color: busy && status !== "recording" ? "oklch(0.65 0.008 250)" : "white",
          boxShadow: canRun ? "0 10px 28px oklch(0.4 0.19 265 / 0.42)" : "none",
          transform: canRun && hover ? "scale(1.03)" : undefined,
          animation: status === "recording" ? "nl-ring 1.4s ease-out infinite" : undefined,
        }}
      >
        <span aria-hidden className="text-[22px]">
          {status === "recording" ? "■" : "🎙"}
        </span>
        {label}
      </button>

      {status === "error" && errorMessage && (
        <div className="text-[12.5px] font-semibold" style={{ color: "oklch(0.55 0.17 25)" }}>
          {errorMessage}
        </div>
      )}
    </div>
  );
}
