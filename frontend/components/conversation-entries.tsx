import { PriorityBadge } from "@/components/priority-badge";
import { css } from "@/lib/css";
import type { ConversationEntry } from "@/lib/types";

export function ConversationEntries({
  entries,
  variant = "archived",
  playingAudio = false,
  onPlayAudio,
}: {
  entries: ConversationEntry[];
  /** "live" shows the audio playback control + VAS detail (robot screen); "archived" omits them (nurse history detail). */
  variant?: "live" | "archived";
  playingAudio?: boolean;
  onPlayAudio?: () => void;
}) {
  return (
    <div className="flex flex-col gap-[14px]">
      {entries.map((entry, i) => (
        <div key={i} className="animate-[nl-fade-in_0.4s_ease]">
          {entry.kind === "system" && (
            <div
              className="flex items-center gap-[10px] px-1 py-1 text-[13px]"
              style={css("color:oklch(0.55 0.015 250);")}
            >
              <span
                className="h-[6px] w-[6px] shrink-0 rounded-full"
                style={css("background:oklch(0.4 0.14 265);")}
              />
              {entry.text}
            </div>
          )}

          {(entry.kind === "robot" || entry.kind === "robot-audio") && (
            <div className="flex items-start gap-[10px]">
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] text-[12px] font-bold text-white"
                style={css("background:oklch(0.4 0.14 265);")}
              >
                N
              </div>
              <div
                className="flex min-w-0 max-w-[80%] items-center gap-[10px] rounded-[4px_12px_12px_12px] px-[14px] py-[10px] text-[14px]"
                style={css("background:oklch(0.93 0.025 265); color:oklch(0.22 0.01 265);")}
              >
                <span>{entry.text}</span>
                {variant === "live" && entry.kind === "robot-audio" && (
                  <button
                    type="button"
                    onClick={onPlayAudio}
                    className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full border-none bg-white text-[10px]"
                    style={css("color:oklch(0.45 0.14 265);")}
                  >
                    {playingAudio ? "■" : "▶"}
                  </button>
                )}
              </div>
            </div>
          )}

          {entry.kind === "patient" && (
            <div className="flex items-start justify-end gap-[10px]">
              <div
                className="max-w-[80%] min-w-0 rounded-[8px_4px_12px_12px] px-[14px] py-[10px] text-[14px] text-white"
                style={css("background:oklch(0.16 0.01 265);")}
              >
                {entry.text}
              </div>
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] text-[12px] font-bold"
                style={css("background:oklch(0.85 0.004 260); color:oklch(0.4 0.004 260);")}
              >
                {entry.initial}
              </div>
            </div>
          )}

          {entry.kind === "classification" && (
            <div
              className="ml-[38px] flex flex-col gap-[10px] rounded-[8px] border p-4"
              style={css("border-color:oklch(0.9 0.003 260); background:oklch(0.97 0.002 260);")}
            >
              <div
                className="text-[11px] font-bold tracking-[0.03em]"
                style={css("color:oklch(0.55 0.015 250);")}
              >
                分類結果
              </div>
              <div className="flex flex-wrap gap-2">
                <span
                  className="rounded-[6px] px-[11px] py-[5px] text-[12.5px] font-semibold"
                  style={css("background:oklch(0.93 0.025 265); color:oklch(0.4 0.14 265);")}
                >
                  {entry.category}
                </span>
                <PriorityBadge priority={entry.priority} />
              </div>
              <div
                className="flex items-center gap-[6px] text-[13px]"
                style={css("color:oklch(0.45 0.015 250);")}
              >
                <span style={css("color:oklch(0.65 0.01 250);")}>ルート →</span> {entry.route}
              </div>
              {variant === "live" && entry.moodLabel && (
                <div
                  className="flex items-center gap-[8px] text-[12px]"
                  style={css("color:oklch(0.5 0.015 250);")}
                >
                  <span
                    className="rounded-[6px] px-[9px] py-[3px] font-semibold"
                    style={css("background:oklch(0.95 0.005 250);")}
                  >
                    体調: {entry.moodLabel}
                  </span>
                  {entry.autoEscalated && (
                    <span className="font-semibold" style={css("color:oklch(0.55 0.17 25);")}>
                      ⚠ 体調の申告により優先度を自動引き上げ
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {entry.kind === "complete" && (
            <div
              className="ml-[38px] flex items-center gap-2 rounded-[8px] px-[14px] py-[10px] text-[13px] font-semibold"
              style={css("background:oklch(0.95 0.04 150); color:oklch(0.4 0.09 150);")}
            >
              <span>✓</span> {entry.text}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
