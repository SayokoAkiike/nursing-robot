import type { MoodId } from "@/lib/types";

const MOUTHS: Record<MoodId, string> = {
  worst: "M8 17c1-2.5 3-3.5 4-3.5s3 1 4 3.5",
  bad: "M8 16.3c1-1 3-1.5 4-1.5s3 .5 4 1.5",
  neutral: "M8 15h8",
  good: "M8 15c1 1.2 3 1.8 4 1.8s3-.6 4-1.8",
  great: "M8 14c1 2.5 3 3.5 4 3.5s3-1 4-3.5",
};

export function MoodIcon({ id, color }: { id: MoodId; color: string }) {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6">
      <circle cx="12" cy="12" r="9" />
      <circle cx="9" cy="10" r="1" fill={color} stroke="none" />
      <circle cx="15" cy="10" r="1" fill={color} stroke="none" />
      <path d={MOUTHS[id]} strokeLinecap="round" />
    </svg>
  );
}
