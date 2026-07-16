"use client";

import { useHover } from "@/hooks/use-hover";
import { MoodSelector } from "@/components/bedside/mood-selector";
import { QuickRequestGrid } from "@/components/bedside/quick-request-grid";
import { ScheduleView } from "@/components/bedside/schedule-view";
import { VoiceRecorderPanel, type VoiceTurnResult } from "@/components/voice/voice-recorder-panel";
import type { ChatMessage, MoodId, QuickRequest } from "@/lib/types";

export type PatientOption = { id: string; label: string };

export function BedsideScreen({
  view,
  patients,
  bedsidePatientId,
  bedsidePatientLabel,
  onSelectPatient,
  onGoToSchedule,
  onBackFromSchedule,
  onSendQuickRequest,
  flashText,
  moodId,
  onSelectMood,
  onReportMood,
  chat,
  chatInput,
  onChatInputChange,
  onSendChat,
  emergencySent,
  onTriggerEmergency,
  onVoiceRequest,
}: {
  view: "home" | "schedule";
  patients: PatientOption[];
  bedsidePatientId: string;
  bedsidePatientLabel: string;
  onSelectPatient: (id: string) => void;
  onGoToSchedule: () => void;
  onBackFromSchedule: () => void;
  onSendQuickRequest: (request: QuickRequest) => void;
  flashText: string;
  moodId: MoodId;
  onSelectMood: (id: MoodId) => void;
  onReportMood: () => void;
  chat: ChatMessage[];
  chatInput: string;
  onChatInputChange: (value: string) => void;
  onSendChat: () => void;
  emergencySent: boolean;
  onTriggerEmergency: () => void;
  onVoiceRequest: (result: VoiceTurnResult) => void;
}) {
  if (view === "schedule") {
    return <ScheduleView patientLabel={bedsidePatientLabel} onBack={onBackFromSchedule} />;
  }
  return (
    <div className="flex animate-[nl-fade-in_0.35s_ease] flex-col gap-5">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div
            className="mb-2 inline-block rounded-[6px] px-2.5 py-[3px] text-[11px] font-bold"
            style={{ background: "oklch(0.93 0.025 265)", color: "oklch(0.4 0.14 265)" }}
          >
            ベッドサイド タブレット端末
          </div>
          <h1 className="m-0 mb-1 text-[22px] font-bold tracking-[-0.01em]">
            {bedsidePatientLabel}、こんにちは
          </h1>
        </div>
        <select
          value={bedsidePatientId}
          onChange={(e) => onSelectPatient(e.target.value)}
          className="shrink-0 rounded-[8px] border bg-white px-2.5 py-2 text-[12.5px]"
          style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.5 0.015 250)" }}
        >
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </header>

      <ScheduleLinkButton onClick={onGoToSchedule} />

      <div
        className="flex flex-col gap-3.5 rounded-[10px] border bg-white p-5"
        style={{ borderColor: "oklch(0.9 0.003 260)" }}
      >
        <div className="text-[13px] font-bold" style={{ color: "oklch(0.4 0.015 250)" }}>
          気軽にリクエスト
        </div>
        <QuickRequestGrid onSend={onSendQuickRequest} />

        {flashText && (
          <div
            className="rounded-[8px] px-3.5 py-2.5 text-[13px] font-semibold"
            style={{ background: "oklch(0.95 0.04 150)", color: "oklch(0.4 0.09 150)" }}
          >
            ✓ {flashText}
          </div>
        )}

        <div
          className="flex flex-col gap-2.5 border-t pt-2"
          style={{ borderColor: "oklch(0.93 0.003 260)" }}
        >
          <span className="text-[12px] font-semibold" style={{ color: "oklch(0.5 0.015 250)" }}>
            いつもと比べて、今の調子は？
          </span>
          <MoodSelector selectedId={moodId} onSelect={onSelectMood} />
          <ReportMoodButton onClick={onReportMood} />

        </div>
      </div>

      <VoiceRecorderPanel label="音声でリクエストを伝える" onResult={onVoiceRequest} />

      <div
        className="flex flex-col gap-3 rounded-[10px] border bg-white p-5"
        style={{ borderColor: "oklch(0.9 0.003 260)" }}
      >
        <div className="text-[13px] font-bold" style={{ color: "oklch(0.4 0.015 250)" }}>
          看護師とのチャット
        </div>
        <div className="flex max-h-[220px] flex-col gap-2 overflow-y-auto">
          {chat.map((m, i) => (
            <div key={i} className={`flex ${m.from === "patient" ? "justify-end" : "justify-start"}`}>
              <div
                className="max-w-[78%] px-3.5 py-2.5 text-[13.5px] leading-[1.5]"
                style={{
                  borderRadius: m.from === "patient" ? "12px 4px 12px 12px" : "4px 12px 12px 12px",
                  background: m.from === "patient" ? "oklch(0.16 0.01 265)" : "oklch(0.93 0.025 265)",
                  color: m.from === "patient" ? "white" : "oklch(0.22 0.01 265)",
                }}
              >
                {m.text}
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="メッセージを入力…"
            value={chatInput}
            onChange={(e) => onChatInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSendChat();
            }}
            className="box-border flex-1 rounded-[8px] border px-3 py-2.5 text-[13.5px]"
            style={{ borderColor: "oklch(0.88 0.003 260)" }}
          />
          <SendChatButton onClick={onSendChat} />
        </div>
      </div>

      <button
        type="button"
        onClick={onTriggerEmergency}
        className="box-border w-full rounded-[8px] border-none px-4 py-4 text-[15px] font-bold text-white"
        style={{
          background: "oklch(0.55 0.19 25)",
          animation: emergencySent ? "nl-ring 1s ease-out infinite" : undefined,
        }}
      >
        {emergencySent ? "緊急通報を送信しました。まもなくスタッフが伺います。" : "緊急呼び出し"}
      </button>
    </div>
  );
}

function ReportMoodButton({ onClick }: { onClick: () => void }) {
  const { hover, hoverHandlers } = useHover();
  return (
    <button
      type="button"
      onClick={onClick}
      {...hoverHandlers}
      className="self-start rounded-[8px] border-none px-4 py-[9px] text-[13px] font-semibold text-white transition-colors duration-150"
      style={{ background: hover ? "oklch(0.1 0.006 265)" : "oklch(0.16 0.01 265)" }}
    >
      今日の調子を伝える
    </button>
  );
}

function SendChatButton({ onClick }: { onClick: () => void }) {
  const { hover, hoverHandlers } = useHover();
  return (
    <button
      type="button"
      onClick={onClick}
      {...hoverHandlers}
      className="rounded-[8px] border-none px-4 py-2.5 text-[13px] font-semibold text-white transition-colors duration-150"
      style={{ background: hover ? "oklch(0.34 0.13 265)" : "oklch(0.4 0.14 265)" }}
    >
      送信
    </button>
  );
}

function ScheduleLinkButton({ onClick }: { onClick: () => void }) {
  const { hover, hoverHandlers } = useHover();
  return (
    <button
      type="button"
      onClick={onClick}
      {...hoverHandlers}
      className="flex items-center justify-between rounded-[10px] border bg-white px-5 py-4 text-left transition-colors duration-150"
      style={{ borderColor: hover ? "oklch(0.75 0.09 265)" : "oklch(0.9 0.003 260)" }}
    >
      <span className="text-[14px] font-semibold" style={{ color: "oklch(0.28 0.015 250)" }}>
        今日の予定を見る
      </span>
      <span className="text-[16px]" style={{ color: "oklch(0.4 0.14 265)" }}>
        →
      </span>
    </button>
  );
}
