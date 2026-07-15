import { Badge } from "@/components/ui/badge";
import { css } from "@/lib/css";
import { PRIORITY_META } from "@/lib/mock-data";
import type { Priority } from "@/lib/types";

export function PriorityBadge({
  priority,
  className,
}: {
  priority: Priority;
  className?: string;
}) {
  const meta = PRIORITY_META[priority];
  return (
    <Badge
      className={`h-auto rounded-md px-[11px] py-[5px] text-[12.5px] font-semibold ${className ?? ""}`}
      style={css(meta.badge)}
    >
      {meta.label}
    </Badge>
  );
}
