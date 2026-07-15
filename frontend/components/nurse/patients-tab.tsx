import { PriorityBadge } from "@/components/priority-badge";
import type { Priority } from "@/lib/types";

export type PatientOverviewVm = {
  id: string;
  name: string;
  room: string;
  initial: string;
  hasRequest: boolean;
  priority: Priority | null;
  requestText: string;
  timeLabel: string;
  canResolve: boolean;
  canDismiss: boolean;
  onResolve: () => void;
  onDismiss: () => void;
};

export function PatientsTab({ patients }: { patients: PatientOverviewVm[] }) {
  return (
    <div
      className="grid gap-4"
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}
    >
      {patients.map((po) => (
        <div
          key={po.id}
          className="flex flex-col gap-3 rounded-[10px] border bg-white p-[18px]"
          style={{ borderColor: "oklch(0.9 0.003 260)" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[14px] font-bold"
              style={{ background: "oklch(0.9 0.004 260)", color: "oklch(0.4 0.004 260)" }}
            >
              {po.initial}
            </div>
            <div className="flex-1">
              <div className="text-[15.5px] font-bold">{po.name}</div>
              <div className="text-[12px]" style={{ color: "oklch(0.55 0.015 250)" }}>
                {po.room}
              </div>
            </div>
            {po.hasRequest && po.priority && (
              <PriorityBadge priority={po.priority} className="text-[11.5px]" />
            )}
          </div>
          <div
            className="min-h-[38px] text-[13.5px] leading-[1.5]"
            style={{ color: "oklch(0.35 0.015 250)" }}
          >
            {po.requestText}
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11.5px]" style={{ color: "oklch(0.6 0.01 250)" }}>
              {po.timeLabel}
            </span>
            {po.canResolve && (
              <button
                type="button"
                onClick={po.onResolve}
                className="rounded-[6px] border-none px-3.5 py-[7px] text-[12.5px] font-semibold text-white"
                style={{ background: "oklch(0.4 0.14 265)" }}
              >
                対応済みにする
              </button>
            )}
            {po.canDismiss && (
              <button
                type="button"
                onClick={po.onDismiss}
                className="rounded-[6px] border px-3.5 py-[7px] text-[12.5px] font-semibold"
                style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.5 0.015 250)" }}
              >
                リストから消す
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
