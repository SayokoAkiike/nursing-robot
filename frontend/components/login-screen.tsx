import { css } from "@/lib/css";
import type { DeviceType } from "@/lib/types";

export type LoginDeviceVm = {
  id: DeviceType;
  label: string;
  facilityId: string;
  personalId: string;
  onFacilityIdChange: (value: string) => void;
  onPersonalIdChange: (value: string) => void;
  onLogin: () => void;
  onScanQr: () => void;
  qrScanning: boolean;
};

export function LoginScreen({ devices }: { devices: LoginDeviceVm[] }) {
  return (
    <div
      className="mx-auto grid items-start gap-5"
      style={{ maxWidth: 1080, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}
    >
      {devices.map((d) => (
        <div
          key={d.id}
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
            <span className="text-[12.5px] font-semibold tracking-[0.01em] text-white">
              {d.label}
            </span>
          </div>
          <div className="flex flex-col gap-[14px] p-6">
            <div className="flex flex-col gap-2">
              <label className="text-[11.5px] font-semibold" style={css("color:oklch(0.52 0.015 250);")}>
                施設ID
              </label>
              <input
                type="text"
                value={d.facilityId}
                onChange={(e) => d.onFacilityIdChange(e.target.value)}
                placeholder="例: HOSP-001"
                className="box-border rounded-[8px] border px-[11px] py-[9px] text-[13.5px]"
                style={css("border-color:oklch(0.88 0.003 260);")}
              />
              <label className="text-[11.5px] font-semibold" style={css("color:oklch(0.52 0.015 250);")}>
                個人ID
              </label>
              <input
                type="text"
                value={d.personalId}
                onChange={(e) => d.onPersonalIdChange(e.target.value)}
                placeholder="例: N-2201"
                className="box-border rounded-[8px] border px-[11px] py-[9px] text-[13.5px]"
                style={css("border-color:oklch(0.88 0.003 260);")}
              />
            </div>
            <button
              type="button"
              onClick={d.onLogin}
              className="box-border w-full rounded-[8px] border-none py-[11px] text-[13.5px] font-semibold text-white"
              style={css("background:oklch(0.4 0.14 265);")}
            >
              ログイン
            </button>
            <div
              className="flex items-center gap-2 text-[11.5px]"
              style={css("color:oklch(0.65 0.008 250);")}
            >
              <div className="h-px flex-1" style={css("background:oklch(0.91 0.003 260);")} />
              または
              <div className="h-px flex-1" style={css("background:oklch(0.91 0.003 260);")} />
            </div>
            <button
              type="button"
              onClick={d.onScanQr}
              className="box-border flex w-full items-center justify-center gap-2 rounded-[8px] border bg-white py-[11px] text-[13px] font-semibold"
              style={css("border-color:oklch(0.88 0.003 260); color:oklch(0.3 0.015 265);")}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="3" y="3" width="7" height="7" />
                <rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" />
                <path d="M14 14h3v3h-3zM19 14h2v2h-2zM14 19h2v2h-2zM19 19h2v2h-2z" />
              </svg>
              {d.qrScanning ? "スキャン中…" : "QRコードでログイン"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
