"use client";

import { useState } from "react";
import { useHover } from "@/hooks/use-hover";
import { useVoiceRecorder, type VoiceEngine, type VoiceTurnResult } from "@/hooks/use-voice-recorder";

export type { VoiceEngine, VoiceTurnResult };

export function VoiceRecorderPanel({
  label = "音声で伝える",
  onResult,
  disabled = false,
  disabledLabel = "処理中…",
}: {
  label?: string;
  onResult?: (result: VoiceTurnResult) => void;
  disabled?: boolean;
  disabledLabel?: string;
}) {
  const [lastResult, setLastResult] = useState<VoiceTurnResult | null>(null);
  const { engine, setEngine, status, processingLabel, errorMessage, toggleRecording } = useVoiceRecorder(
    (result) => {
      setLastResult(result);
      onResult?.(result);
    },
  );
  const { hover, hoverHandlers } = useHover();

  const busy = status === "processing" || disabled;

  return (
    <div
      className="flex flex-col gap-3 rounded-[10px] border bg-white p-5"
      style={{ borderColor: "oklch(0.9 0.003 260)" }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-[13px] font-bold" style={{ color: "oklch(0.4 0.015 250)" }}>
          {label}
        </div>
        <select
          value={engine}
          onChange={(e) => setEngine(e.target.value as VoiceEngine)}
          disabled={status === "recording" || busy}
          className="shrink-0 rounded-[8px] border bg-white px-2.5 py-[7px] text-[12.5px]"
          style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.4 0.015 250)" }}
        >
          <option value="ずんだもん">音声エンジン: ずんだもん</option>
          <option value="Gemini Live">音声エンジン: Gemini Live</option>
        </select>
      </div>

      <button
        type="button"
        onClick={toggleRecording}
        disabled={busy}
        {...hoverHandlers}
        className="box-border flex w-full items-center justify-center gap-2.5 rounded-full border-none py-3.5 text-[14.5px] font-bold text-white transition-transform duration-150"
        style={{
          cursor: busy ? "not-allowed" : "pointer",
          background:
            status === "recording"
              ? "oklch(0.55 0.19 25)"
              : busy
                ? "oklch(0.75 0.01 260)"
                : hover
                  ? "oklch(0.1 0.006 265)"
                  : "oklch(0.16 0.01 265)",
          animation: status === "recording" ? "nl-ring 1.4s ease-out infinite" : undefined,
        }}
      >
        <span aria-hidden>{status === "recording" ? "■" : "🎙"}</span>
        {status === "recording"
          ? "録音を終了する"
          : status === "processing"
            ? processingLabel
            : disabled
              ? disabledLabel
              : "マイクで録音する"}
      </button>

      {status === "error" && errorMessage && (
        <div className="text-[12.5px] font-semibold" style={{ color: "oklch(0.55 0.17 25)" }}>
          {errorMessage}
        </div>
      )}

      {lastResult && status !== "processing" && (
        <div
          className="flex flex-col gap-2 rounded-[8px] border-t pt-3"
          style={{ borderColor: "oklch(0.93 0.003 260)" }}
        >
          <div className="text-[12.5px]" style={{ color: "oklch(0.5 0.015 250)" }}>
            <span className="font-semibold">認識テキスト:</span> {lastResult.transcript || "（認識できませんでした）"}
          </div>
          <div className="text-[13.5px]" style={{ color: "oklch(0.22 0.01 265)" }}>
            <span className="font-semibold">応答:</span> {lastResult.responseText}
          </div>
          <audio controls autoPlay src={lastResult.audioUrl} className="w-full" style={{ height: 32 }} />
        </div>
      )}
    </div>
  );
}
