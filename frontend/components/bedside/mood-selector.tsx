import { MoodIcon } from "@/components/icons/mood-icons";
import { MOOD_LEVELS } from "@/lib/mock-data";
import type { MoodId } from "@/lib/types";

export function MoodSelector({
  selectedId,
  onSelect,
}: {
  selectedId: MoodId;
  onSelect: (id: MoodId) => void;
}) {
  return (
    <div className="grid grid-cols-5 gap-2">
      {MOOD_LEVELS.map((m) => {
        const selected = m.id === selectedId;
        const iconColor = selected ? `oklch(0.45 0.13 ${m.hue})` : "oklch(0.75 0.01 250)";
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => onSelect(m.id)}
            className="flex flex-col items-center gap-1.5 rounded-[8px] border px-1.5 py-2.5"
            style={{
              borderColor: selected ? `oklch(0.75 0.09 ${m.hue})` : "oklch(0.91 0.003 260)",
              background: selected ? `oklch(0.95 0.03 ${m.hue})` : "white",
            }}
          >
            <MoodIcon id={m.id} color={iconColor} />
            <span
              className="text-[10.5px]"
              style={{
                color: selected ? "oklch(0.4 0.02 250)" : "oklch(0.6 0.01 250)",
                fontWeight: selected ? 700 : 500,
              }}
            >
              {m.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
