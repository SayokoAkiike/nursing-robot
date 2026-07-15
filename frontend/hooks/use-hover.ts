import { useState, useCallback } from "react";

export function useHover() {
  const [hover, setHover] = useState(false);
  const onMouseEnter = useCallback(() => setHover(true), []);
  const onMouseLeave = useCallback(() => setHover(false), []);
  return { hover, hoverHandlers: { onMouseEnter, onMouseLeave } };
}
