"use client";

import { useHover } from "@/hooks/use-hover";
import { ConversationEntries } from "@/components/conversation-entries";
import { StageTracker } from "@/components/robot/stage-tracker";
import { VoiceRecorderPanel, type VoiceTurnResult } from "@/components/voice/voice-recorder-panel";
import type { PatientOption } from "@/components/bedside/bedside-screen";
import type { ConversationEntry } from "@/lib/types";

export function RobotScreen({
  patients,
  selectedPatientId,
  onSelectPatient,
  isRunning,
  onRunPatrol,
  patientBannerLabel,
  patientBannerName,
  patientInitial,
  stepRevealCount,
  revealedEntries,
  hasCaption,
  robotCaptionText,
  patientCaptionText,
  robotCaptionActive,
  patientCaptionActive,
  playingAudio,
  onPlayAudio,
  onVoiceTurnResult,
}: {
  patients: PatientOption[];
  selectedPatientId: string;
  onSelectPatient: (id: string) => void;
  isRunning: boolean;
  onRunPatrol: () => void;
  patientBannerLabel: string;
  patientBannerName: string;
  patientInitial: string;
  stepRevealCount: number;
  revealedEntries: ConversationEntry[];
  hasCaption: boolean;
  robotCaptionText: string;
  patientCaptionText: string;
  robotCaptionActive: boolean;
  patientCaptionActive: boolean;
  playingAudio: boolean;
  onPlayAudio: () => void;
  onVoiceTurnResult: (result: VoiceTurnResult) => void;
}) {
  return (
    <div className="flex flex-col gap-5">
      <div
        className="flex flex-col gap-5 rounded-[10px] border bg-white p-6"
        style={{ borderColor: "oklch(0.9 0.003 260)" }}
      >
        <div>
          <label className="mb-2 block text-[12px] font-semibold" style={{ color: "oklch(0.52 0.015 250)" }}>
            患者を選択
          </label>
          <select
            value={selectedPatientId}
            onChange={(e) => onSelectPatient(e.target.value)}
            className="w-full rounded-[8px] border px-3 py-2.5 text-[14px]"
            style={{ borderColor: "oklch(0.88 0.003 260)", background: "oklch(0.97 0.002 260)" }}
          >
            {patients.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <TalkButton disabled={isRunning} onClick={onRunPatrol} label={isRunning ? "はなしかけ中…" : "話しかける（デモシナリオ）"} />
      </div>

      <VoiceRecorderPanel label="実際に話しかけてみる（実音声）" onResult={onVoiceTurnResult} />

      <div
        className="flex min-h-[520px] min-w-0 flex-col rounded-[10px] border bg-white p-2"
        style={{ borderColor: "oklch(0.9 0.003 260)" }}
      >
        <div
          className="flex min-w-0 flex-col gap-3.5 border-b px-5 py-[18px]"
          style={{ borderColor: "oklch(0.93 0.003 260)" }}
        >
          <div className="text-[14px] font-bold">{patientBannerLabel}</div>
          <StageTracker stepRevealCount={stepRevealCount} />
        </div>

        {hasCaption && (
          <div
            className="grid min-w-0 grid-cols-2 gap-6 border-b p-6"
            style={{ borderColor: "oklch(0.93 0.003 260)", background: "oklch(0.16 0.01 265)" }}
          >
            <div
              className="min-w-0 transition-opacity duration-200"
              style={{ opacity: robotCaptionActive || stepRevealCount === 0 ? 1 : 0.4 }}
            >
              <div className="mb-2.5 flex items-center gap-2">
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px] text-[11px] font-bold text-white"
                  style={{ background: "oklch(0.4 0.19 265)" }}
                >
                  N
                </span>
                <span
                  className="text-[11.5px] font-bold tracking-[0.03em]"
                  style={{ color: "oklch(0.75 0.09 265)" }}
                >
                  みまもりロボット
                </span>
              </div>
              <div
                className="min-h-[1.45em] text-[24px] leading-[1.45] font-bold break-words text-white"
                style={{ overflowWrap: "break-word" }}
              >
                {robotCaptionText}
              </div>
            </div>
            <div
              className="min-w-0 border-l pl-6 transition-opacity duration-200"
              style={{
                borderColor: "oklch(0.3 0.02 265)",
                opacity: patientCaptionActive || stepRevealCount === 0 ? 1 : 0.4,
              }}
            >
              <div className="mb-2.5 flex items-center gap-2">
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px] text-[11px] font-bold"
                  style={{ background: "oklch(0.85 0.004 260)", color: "oklch(0.3 0.004 260)" }}
                >
                  {patientInitial}
                </span>
                <span
                  className="text-[11.5px] font-bold tracking-[0.03em]"
                  style={{ color: "oklch(0.7 0.01 260)" }}
                >
                  {patientBannerName}
                </span>
              </div>
              <div
                className="min-h-[1.45em] text-[24px] leading-[1.45] font-bold break-words text-white"
                style={{ overflowWrap: "break-word" }}
              >
                {patientCaptionText}
              </div>
            </div>
          </div>
        )}

        <div
          className="border-b px-5 py-4 text-[13px] font-semibold"
          style={{ borderColor: "oklch(0.93 0.003 260)", color: "oklch(0.4 0.015 250)" }}
        >
          リクエスト履歴
        </div>

        {revealedEntries.length === 0 && (
          <div
            className="flex flex-1 items-center justify-center px-5 py-[60px] text-center text-[13.5px]"
            style={{ color: "oklch(0.7 0.008 250)" }}
          >
            「話しかける」を押すと、
            <br />
            ここに会話の履歴と分類結果が表示されます。
          </div>
        )}

        <div className="p-5">
          <ConversationEntries
            entries={revealedEntries}
            variant="live"
            playingAudio={playingAudio}
            onPlayAudio={onPlayAudio}
          />
        </div>
      </div>
    </div>
  );
}

function TalkButton({
  disabled,
  onClick,
  label,
}: {
  disabled: boolean;
  onClick: () => void;
  label: string;
}) {
  const { hover, hoverHandlers } = useHover();
  const canRun = !disabled;
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      {...hoverHandlers}
      className="box-border flex w-full items-center justify-center gap-3 rounded-full border-none py-[26px] text-[19px] font-bold transition-transform duration-150"
      style={{
        cursor: canRun ? "pointer" : "not-allowed",
        background: canRun ? "oklch(0.4 0.19 265)" : "oklch(0.9 0.003 260)",
        color: canRun ? "white" : "oklch(0.65 0.008 250)",
        boxShadow: canRun ? "0 10px 28px oklch(0.4 0.19 265 / 0.42)" : "none",
        transform: canRun && hover ? "scale(1.03)" : undefined,
      }}
    >
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 4v-4H6a2 2 0 0 1-2-2Z" />
      </svg>
      {label}
    </button>
  );
}
