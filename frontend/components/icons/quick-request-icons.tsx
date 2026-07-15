import type { QuickRequestKind } from "@/lib/types";

const common = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function QuickRequestIcon({ kind }: { kind: QuickRequestKind }) {
  switch (kind) {
    case "toilet":
      return (
        <svg {...common}>
          <rect x="7" y="3" width="10" height="4" rx="1" />
          <path d="M6 9c0 6 2 10 6 10s6-4 6-10" />
        </svg>
      );
    case "drip":
      return (
        <svg {...common}>
          <rect x="9" y="3" width="6" height="6" rx="1" />
          <path d="M12 9v3" />
          <path d="M12 12c-2.2 2-3 3.6-3 5.2A3 3 0 0 0 12 20a3 3 0 0 0 3-2.8c0-1.6-.8-3.2-3-5.2Z" />
        </svg>
      );
    case "reposition":
      return (
        <svg {...common}>
          <path d="M4 12a8 8 0 0 1 14-5.3" />
          <path d="M20 12a8 8 0 0 1-14 5.3" />
          <path d="M18 3v4h-4" />
          <path d="M6 21v-4h4" />
        </svg>
      );
    case "suction":
      return (
        <svg {...common}>
          <path d="M5 5h14l-5 7v6h-4v-6Z" />
        </svg>
      );
    case "medicine":
      return (
        <svg {...common}>
          <rect x="3" y="9" width="18" height="6" rx="3" />
          <path d="M12 9v6" />
        </svg>
      );
    case "water":
      return (
        <svg {...common}>
          <path d="M12 3c4 5 6 8.5 6 11.5A6 6 0 0 1 6 14.5C6 11.5 8 8 12 3Z" />
        </svg>
      );
  }
}
