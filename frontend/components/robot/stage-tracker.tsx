import { ROBOT_STAGE_DEFS } from "@/lib/mock-data";

export function StageTracker({ stepRevealCount }: { stepRevealCount: number }) {
  return (
    <div className="flex min-w-0 items-start">
      {ROBOT_STAGE_DEFS.map((sd, i) => {
        const prevThreshold = i === 0 ? 0 : ROBOT_STAGE_DEFS[i - 1].threshold;
        const done = stepRevealCount >= sd.threshold;
        const active = !done && stepRevealCount >= prevThreshold && stepRevealCount > 0;
        const isLast = i === ROBOT_STAGE_DEFS.length - 1;
        return (
          <div key={sd.label} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-0 max-w-full flex-col items-center gap-1.5">
              <div
                className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                style={
                  done
                    ? { background: "oklch(0.4 0.14 265)", color: "white" }
                    : active
                      ? {
                          background: "oklch(0.93 0.025 265)",
                          color: "oklch(0.4 0.14 265)",
                          border: "2px solid oklch(0.4 0.14 265)",
                        }
                      : { background: "oklch(0.93 0.003 260)", color: "oklch(0.6 0.004 260)" }
                }
              >
                {done ? "✓" : ""}
              </div>
              <span
                className="text-[11px] font-semibold whitespace-nowrap"
                style={{ color: done || active ? "oklch(0.25 0.01 265)" : "oklch(0.62 0.003 260)" }}
              >
                {sd.label}
              </span>
            </div>
            {!isLast && (
              <div
                className="mx-1.5 h-0.5 flex-1"
                style={{ background: done ? "oklch(0.4 0.14 265)" : "oklch(0.9 0.003 260)" }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
