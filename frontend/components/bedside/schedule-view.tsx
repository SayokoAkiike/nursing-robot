import { useHover } from "@/hooks/use-hover";
import { SCHEDULE_ITEMS } from "@/lib/mock-data";

export function ScheduleView({
  patientLabel,
  onBack,
}: {
  patientLabel: string;
  onBack: () => void;
}) {
  const { hover, hoverHandlers } = useHover();
  return (
    <div className="flex animate-[nl-fade-in_0.35s_ease] flex-col gap-5">
      <button
        type="button"
        onClick={onBack}
        {...hoverHandlers}
        className="flex items-center gap-1.5 self-start border-none bg-transparent p-0 text-[13px] font-semibold transition-opacity duration-150"
        style={{ color: "oklch(0.4 0.14 265)", opacity: hover ? 0.65 : 1 }}
      >
        ← 戻る
      </button>
      <header>
        <h1 className="mb-1 text-[20px] font-bold tracking-[-0.01em]">今日の予定</h1>
        <p className="m-0 text-[13.5px]" style={{ color: "oklch(0.52 0.015 250)" }}>
          {patientLabel}さんの本日の予定と処置内容です。
        </p>
      </header>
      <div
        className="flex flex-col gap-4 rounded-[10px] border bg-white p-5"
        style={{ borderColor: "oklch(0.9 0.003 260)" }}
      >
        {SCHEDULE_ITEMS.map((item, i) => {
          const done = item.status === "done";
          return (
            <div key={i} className="flex items-center gap-3">
              <div
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: done ? "oklch(0.6 0.13 150)" : "oklch(0.4 0.14 265)" }}
              />
              <div
                className="w-[52px] shrink-0 text-[12.5px] font-semibold"
                style={{ color: "oklch(0.45 0.015 250)" }}
              >
                {item.time}
              </div>
              <div className="flex-1">
                <div className="text-[14.5px] font-semibold" style={{ color: "oklch(0.25 0.015 250)" }}>
                  {item.task}
                </div>
                <div className="text-[12px]" style={{ color: "oklch(0.58 0.015 250)" }}>
                  {item.note}
                </div>
              </div>
              <div
                className="rounded-[6px] px-2.5 py-[3px] text-[11.5px] font-semibold"
                style={
                  done
                    ? { background: "oklch(0.95 0.04 150)", color: "oklch(0.4 0.09 150)" }
                    : { background: "oklch(0.93 0.025 265)", color: "oklch(0.4 0.14 265)" }
                }
              >
                {done ? "完了" : "予定"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
