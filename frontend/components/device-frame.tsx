import type { ReactNode } from "react";
import { css } from "@/lib/css";

export function DeviceFrame({
  title,
  maxWidth,
  onSwitchDevice,
  rightBadge,
  children,
}: {
  title: string;
  maxWidth: number;
  onSwitchDevice: () => void;
  rightBadge?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto" style={{ maxWidth }}>
      <section
        className="flex flex-col overflow-hidden rounded-xl border"
        style={css("background:oklch(0.97 0.002 260); border-color:oklch(0.9 0.003 260);")}
      >
        <div
          className="flex items-center gap-2 px-5 py-[14px]"
          style={css("background:oklch(0.14 0.004 260);")}
        >
          <span
            className="h-[7px] w-[7px] shrink-0 rounded-full"
            style={css("background:oklch(0.55 0.14 150);")}
          />
          <span className="flex-1 text-[12.5px] font-semibold tracking-[0.01em] text-white">
            {title}
          </span>
          <button
            type="button"
            onClick={onSwitchDevice}
            className="mr-2 border-none bg-transparent text-[11.5px]"
            style={css("color:oklch(0.75 0.01 260);")}
          >
            端末を切り替える
          </button>
          {rightBadge}
        </div>
        <div className="animate-[nl-fade-in_0.35s_ease] p-7">{children}</div>
      </section>
    </div>
  );
}
