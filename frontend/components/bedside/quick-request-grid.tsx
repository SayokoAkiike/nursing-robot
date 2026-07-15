import { QuickRequestIcon } from "@/components/icons/quick-request-icons";
import { useHover } from "@/hooks/use-hover";
import { QUICK_REQUESTS } from "@/lib/mock-data";
import type { QuickRequest } from "@/lib/types";

function QuickRequestTile({ request, onSend }: { request: QuickRequest; onSend: () => void }) {
  const { hover, hoverHandlers } = useHover();
  return (
    <button
      type="button"
      onClick={onSend}
      {...hoverHandlers}
      className="flex flex-col items-center gap-2 rounded-[10px] border px-2 py-4 transition-colors duration-150"
      style={{
        borderColor: hover ? "oklch(0.75 0.09 265)" : "oklch(0.91 0.003 260)",
        background: hover ? "oklch(0.95 0.02 265)" : "oklch(0.97 0.002 260)",
      }}
    >
      <span
        className="flex h-10 w-10 items-center justify-center rounded-[8px]"
        style={{ background: "oklch(0.93 0.025 265)", color: "oklch(0.4 0.14 265)" }}
      >
        <QuickRequestIcon kind={request.kind} />
      </span>
      <span className="text-[12.5px] font-semibold" style={{ color: "oklch(0.35 0.006 260)" }}>
        {request.label}
      </span>
    </button>
  );
}

export function QuickRequestGrid({ onSend }: { onSend: (request: QuickRequest) => void }) {
  return (
    <div className="grid grid-cols-3 gap-2.5">
      {QUICK_REQUESTS.map((q) => (
        <QuickRequestTile key={q.kind} request={q} onSend={() => onSend(q)} />
      ))}
    </div>
  );
}
