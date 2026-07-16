"use client";

import { useEffect, useRef, useState } from "react";

export type VoiceEngine = "ずんだもん" | "Gemini Live";

export type VoiceTurnResult = {
  transcript: string;
  responseText: string;
  audioUrl: string;
  backendName: string;
};

export type VoiceRecorderStatus = "idle" | "recording" | "processing" | "error";

const PROCESSING_LABELS = [
  "音声を認識しています…",
  "応答を生成しています…",
  "音声を合成しています…",
];

const PROCESSING_LABEL_INTERVAL_MS = 1300;

/**
 * Shared mic-recording + `/api/voice/respond` submission logic, used by
 * both the bedside tablet's voice request panel and the robot screen's
 * single combined talk button -- the two need the same recording state
 * machine and backend call, just rendered differently.
 */
export function useVoiceRecorder(onResult?: (result: VoiceTurnResult) => void) {
  const [engine, setEngine] = useState<VoiceEngine>("ずんだもん");
  const [status, setStatus] = useState<VoiceRecorderStatus>("idle");
  const [processingLabel, setProcessingLabel] = useState(PROCESSING_LABELS[0]);
  const [errorMessage, setErrorMessage] = useState("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const labelTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  const toggleRecording = () => {
    if (status === "recording") {
      stopRecording();
    } else {
      void startRecording();
    }
  };

  return {
    engine,
    setEngine,
    status,
    processingLabel,
    errorMessage,
    startRecording,
    stopRecording,
    toggleRecording,
  };
}
