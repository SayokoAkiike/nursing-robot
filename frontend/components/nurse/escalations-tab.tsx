import { PriorityBadge } from "@/components/priority-badge";
import { PRIORITY_META } from "@/lib/mock-data";
import type { EscalationStatus, Priority } from "@/lib/types";

export type EscalationVm = {
  id: string;
  patient: string;
  room: string;
  request: string;
  time: string;
  initial: string;
  priority: Priority;
  status: EscalationStatus;
  assignedNurse: string | null;
  recallLabel: string;
  callLabel: string;
  onAcknowledge: () => void;
  onResolve: () => void;
  onRecall: () => void;
  onCallPatient: () => void;
};

export function EscalationsTab({
  dashTab,
  onSetDashTab,
  activeCount,
  resolvedCount,
  escalations,
}: {
  dashTab: "open" | "resolved";
  onSetDashTab: (tab: "open" | "resolved") => void;
  activeCount: number;
  resolvedCount: number;
  escalations: EscalationVm[];
}) {
  const tabBase =
    "rounded-[8px] border-none px-[18px] py-[9px] text-[13.5px] font-semibold cursor-pointer";
  return (
    <div>
      <div
        className="mb-[18px] flex w-fit gap-1.5 rounded-[10px] p-1"
        style={{ background: "oklch(0.95 0.003 260)" }}
      >
        <button
          type="button"
          onClick={() => onSetDashTab("open")}
          className={tabBase}
          style={
            dashTab === "open"
              ? { background: "white", color: "oklch(0.25 0.01 265)", boxShadow: "0 1px 2px oklch(0 0 0 / 0.05)" }
              : { background: "transparent", color: "oklch(0.55 0.01 250)" }
          }
        >
          対応中 ({activeCount})
        </button>
        <button
          type="button"
          onClick={() => onSetDashTab("resolved")}
          className={tabBase}
          style={
            dashTab === "resolved"
              ? { background: "white", color: "oklch(0.25 0.01 265)", boxShadow: "0 1px 2px oklch(0 0 0 / 0.05)" }
              : { background: "transparent", color: "oklch(0.55 0.01 250)" }
          }
        >
          対応済み ({resolvedCount})
        </button>
      </div>

      {escalations.length === 0 && (
        <div
          className="rounded-[10px] border bg-white px-5 py-[60px] text-center text-[14px]"
          style={{ borderColor: "oklch(0.9 0.003 260)", color: "oklch(0.7 0.008 250)" }}
        >
          {dashTab === "open"
            ? "現在、対応が必要なエスカレーションはありません。"
            : "まだ対応済みの項目はありません。"}
        </div>
      )}

      <div
        className="grid gap-4"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))" }}
      >
        {escalations.map((esc) => {
          const meta = PRIORITY_META[esc.priority];
          const isActive = esc.status === "active";
          const isAcknowledged = esc.status === "acknowledged";
          const isResolved = esc.status === "resolved";
          return (
            <div
              key={esc.id}
              className="flex animate-[nl-fade-in_0.3s_ease] flex-col gap-3 rounded-[8px] border border-l-4 bg-white p-[18px]"
              style={{
                borderColor: "oklch(0.91 0.003 260)",
                borderLeftColor: meta.cardBorder,
                opacity: isResolved ? 0.72 : 1,
              }}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <PriorityBadge priority={esc.priority} className="text-[12px]" />
                  {isAcknowledged && (
                    <span
                      className="rounded-[6px] px-[11px] py-[5px] text-[12px] font-semibold"
                      style={{ background: "oklch(0.93 0.025 265)", color: "oklch(0.4 0.14 265)" }}
                    >
                      対応中
                    </span>
                  )}
                </div>
                <span className="text-[12px]" style={{ color: "oklch(0.6 0.01 250)" }}>
                  {esc.time}
                </span>
              </div>

              <div className="flex items-center gap-2.5">
                <div
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[14px] font-bold"
                  style={{ background: "oklch(0.9 0.004 260)", color: "oklch(0.4 0.004 260)" }}
                >
                  {esc.initial}
                </div>
                <div>
                  <div className="text-[16px] font-bold">{esc.patient}</div>
                  <div className="mt-px text-[12.5px]" style={{ color: "oklch(0.55 0.015 250)" }}>
                    {esc.room}
                  </div>
                </div>
              </div>

              <div className="flex-1 text-[14px] leading-[1.5]" style={{ color: "oklch(0.32 0.015 250)" }}>
                「{esc.request}」
              </div>

              {esc.assignedNurse && (
                <div
                  className="flex items-center gap-1.5 text-[12px]"
                  style={{ color: "oklch(0.5 0.015 250)" }}
                >
                  <span
                    className="h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: "oklch(0.4 0.14 265)" }}
                  />
                  担当: {esc.assignedNurse}
                </div>
              )}

              {isActive && (
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={esc.onAcknowledge}
                    className="box-border w-full rounded-[8px] border-none py-2.5 text-[13.5px] font-semibold text-white"
                    style={{ background: "oklch(0.4 0.14 265)" }}
                  >
                    通話を承諾
                  </button>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={esc.onRecall}
                      className="flex-1 rounded-[8px] border py-2 text-[12.5px] font-semibold"
                      style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.4 0.015 250)" }}
                    >
                      {esc.recallLabel}
                    </button>
                    <button
                      type="button"
                      onClick={esc.onCallPatient}
                      className="flex-1 rounded-[8px] border py-2 text-[12.5px] font-semibold"
                      style={{ borderColor: "oklch(0.88 0.003 260)", color: "oklch(0.4 0.015 250)" }}
                    >
                      {esc.callLabel}
                    </button>
                  </div>
                </div>
              )}
              {isAcknowledged && (
                <button
                  type="button"
                  onClick={esc.onResolve}
                  className="box-border w-full rounded-[8px] border-none py-2.5 text-[13.5px] font-semibold text-white"
                  style={{ background: "oklch(0.4 0.14 265)" }}
                >
                  対応完了にする
                </button>
              )}
              {isResolved && (
                <div
                  className="box-border w-full rounded-[8px] py-2.5 text-center text-[13px] font-semibold"
                  style={{ background: "oklch(0.95 0.005 250)", color: "oklch(0.55 0.01 250)" }}
                >
                  ✓ 対応済み
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
