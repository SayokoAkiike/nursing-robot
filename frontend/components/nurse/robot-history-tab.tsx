"use client";

import { useHover } from "@/hooks/use-hover";
import { ConversationEntries } from "@/components/conversation-entries";
import { PriorityBadge } from "@/components/priority-badge";
import type { PatientOption } from "@/components/bedside/bedside-screen";
import type { ConversationEntry, Priority } from "@/lib/types";

export type HistoryBucketVm = {
  label: string;
  records: Array<{
    id: string;
    summary: string;
    priority: Priority;
    timeLabel: string;
    onSelect: () => void;
  }>;
};

export function RobotHistoryTab({
  patients,
  selectedPatientId,
  onSelectPatient,
  mode,
  hasNoHistory,
  buckets,
  selectedRecordTimeLabel,
  selectedRecordEntries,
  onCloseDetail,
}: {
  patients: PatientOption[];
  selectedPatientId: string;
  onSelectPatient: (id: string) => void;
  mode: "list" | "detail";
  hasNoHistory: boolean;
  buckets: HistoryBucketVm[];
  selectedRecordTimeLabel: string;
  selectedRecordEntries: ConversationEntry[];
  onCloseDetail: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <select
        value={selectedPatientId}
        onChange={(e) => onSelectPatient(e.target.value)}
        className="self-start rounded-[8px] border bg-white px-3 py-[9px] text-[13px]"
        style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.3 0.015 250)" }}
      >
        {patients.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
      </select>

      {mode === "list" && (
        <>
          {hasNoHistory && (
            <div
              className="rounded-[10px] border bg-white px-5 py-[60px] text-center text-[14px]"
              style={{ borderColor: "oklch(0.9 0.003 260)", color: "oklch(0.7 0.008 250)" }}
            >
              この患者さんの会話記録はまだありません。
            </div>
          )}
          {buckets.map((bucket) => (
            <div key={bucket.label} className="flex flex-col gap-2">
              <div
                className="text-[12px] font-bold tracking-[0.02em]"
                style={{ color: "oklch(0.55 0.015 250)" }}
              >
                {bucket.label}
              </div>
              {bucket.records.map((rec) => (
                <HistoryRecordButton key={rec.id} record={rec} />
              ))}
            </div>
          ))}
        </>
      )}

      {mode === "detail" && (
        <div
          className="flex min-w-0 flex-col rounded-[10px] border bg-white p-2"
          style={{ borderColor: "oklch(0.9 0.003 260)" }}
        >
          <div
            className="flex items-center gap-3 border-b px-5 py-3.5"
            style={{ borderColor: "oklch(0.93 0.003 260)" }}
          >
            <button
              type="button"
              onClick={onCloseDetail}
              className="border-none bg-transparent p-0 text-[13px] font-semibold"
              style={{ color: "oklch(0.4 0.14 265)" }}
            >
              ← 一覧へ戻る
            </button>
            <span className="text-[12px]" style={{ color: "oklch(0.6 0.01 250)" }}>
              {selectedRecordTimeLabel}
            </span>
          </div>
          <div className="p-5">
            <ConversationEntries entries={selectedRecordEntries} variant="archived" />
          </div>
        </div>
      )}
    </div>
  );
}

function HistoryRecordButton({
  record,
}: {
  record: { id: string; summary: string; priority: Priority; timeLabel: string; onSelect: () => void };
}) {
  const { hover, hoverHandlers } = useHover();
  return (
    <button
      type="button"
      onClick={record.onSelect}
      {...hoverHandlers}
      className="box-border flex w-full items-center gap-3.5 rounded-[10px] border bg-white px-4 py-3.5 text-left transition-colors duration-150"
      style={{ borderColor: hover ? "oklch(0.75 0.09 265)" : "oklch(0.9 0.003 260)" }}
    >
      <PriorityBadge priority={record.priority} className="shrink-0 text-[11.5px]" />
      <span
        className="min-w-0 flex-1 overflow-hidden text-[13.5px] text-ellipsis whitespace-nowrap"
        style={{ color: "oklch(0.28 0.015 250)" }}
      >
        {record.summary}
      </span>
      <span className="shrink-0 text-[11.5px]" style={{ color: "oklch(0.6 0.01 250)" }}>
        {record.timeLabel}
      </span>
      <span className="shrink-0" style={{ color: "oklch(0.75 0.01 260)" }}>
        →
      </span>
    </button>
  );
}
