"use client";

import { useEffect, useRef, useState } from "react";
import { useHover } from "@/hooks/use-hover";

export type VoiceEngine = "ずんだもん" | "Gemini Live";

export type VoiceTurnResult = {
  transcript: string;
  responseText: string;
  audioUrl: string;
  backendName: string;
};

type Status = "idle" | "recording" | "processing" | "error";

const PROCESSING_LABELS = [
  "音声を認識しています…",
  "応答を生成しています…",
  "音声を合成しています…",
];

const PROCESSING_LABEL_INTERVAL_MS = 1300;

export function VoiceRecorderPanel({
  label = "音声で伝える",
  onResult,
}: {
  label?: string;
  onResult?: (result: VoiceTurnResult) => void;
}) {
  const [engine, setEngine] = useState<VoiceEngine>("ずんだもん");
  const [status, setStatus] = useState<Status>("idle");
  const [processingLabel, setProcessingLabel] = useState(PROCESSING_LABELS[0]);
  const [errorMessage, setErrorMessage] = useState("");
  const [lastResult, setLastResult] = useState<VoiceTurnResult | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const labelTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { hover, hoverHandlers } = useHover();

  useEffect(() => {
    return () => {
      if (labelTimerRef.current) clearInterval(labelTimerRef.current);
      mediaRecorderRef.current?.stream.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const submitRecording = async (blob: Blob) => {
    setStatus("processing");
    let labelIndex = 0;
    setProcessingLabel(PROCESSING_LABELS[0]);
    labelTimerRef.current = setInterval(() => {
      labelIndex = (labelIndex + 1) % PROCESSING_LABELS.length;
      setProcessingLabel(PROCESSING_LABELS[labelIndex]);
    }, PROCESSING_LABEL_INTERVAL_MS);

    try {
      const form = new FormData();
      form.append("audio", blob, "recording.webm");
      form.append("backend", engine);
      const res = await fetch("/api/voice/respond", { method: "POST", body: form });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body?.error ?? body?.detail ?? `音声処理に失敗しました（${res.status}）`);
      }
      const result: VoiceTurnResult = {
        transcript: body.transcript,
        responseText: body.response_text,
        audioUrl: `data:audio/wav;base64,${body.response_audio_base64}`,
        backendName: body.backend_name,
      };
      setLastResult(result);
      setStatus("idle");
      onResult?.(result);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "音声処理に失敗しました。");
      setStatus("error");
    } finally {
      if (labelTimerRef.current) {
        clearInterval(labelTimerRef.current);
        labelTimerRef.current = null;
      }
    }
  };

  const startRecording = async () => {
    setErrorMessage("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        void submitRecording(new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" }));
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setStatus("recording");
    } catch {
      setErrorMessage("マイクにアクセスできませんでした。ブラウザのマイク権限をご確認ください。");
      setStatus("error");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const busy = status === "processing";

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
        onClick={status === "recording" ? stopRecording : startRecording}
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
          : busy
            ? processingLabel
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
