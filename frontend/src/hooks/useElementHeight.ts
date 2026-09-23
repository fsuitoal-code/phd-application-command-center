import { useEffect, useRef, useState, type RefObject } from "react";

/**
 * An element's live rendered height, for stacking sticky blocks below one
 * another when each one's height can change (a wrapping title, an opened
 * edit form, a research-status strip). `deps` should include anything that
 * changes the element's content — the ref only attaches once the element
 * actually mounts, so a dep gated behind a loading check (e.g. `if (!p)
 * return`) needs to be listed here to re-run after that first mount.
 */
export function useElementHeight<T extends HTMLElement>(
  ...deps: unknown[]
): [RefObject<T | null>, number] {
  const ref = useRef<T>(null);
  const [height, setHeight] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const setH = () => setHeight(el.offsetHeight);
    setH();
    const ro = new ResizeObserver(setH);
    ro.observe(el);
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return [ref, height];
}
