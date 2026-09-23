import { useEffect, useRef, useState } from "react";

/**
 * Drag-to-reorder for any manually ordered list — programs, steps, deadlines,
 * requirements, notes, faculty, faculty notes. One implementation, so every
 * list drags, drops and recovers from a failed save the same way.
 *
 * The dragged index lives in a ref, not state: dragover/drop can fire before
 * React has re-rendered after dragstart, and a stale closure would drop the
 * reorder on the floor. State mirrors it only for the visual feedback.
 *
 * `items` must be referentially stable between renders (props or state, not a
 * fresh `?? []`), since the local order resyncs whenever it changes.
 */
export function useReorder<T extends { id: number }>(
  items: T[],
  save: (ids: number[]) => Promise<unknown>,
  { onSettled, onError }: { onSettled: () => void; onError: (e: unknown) => void },
) {
  const [order, setOrder] = useState<T[]>(items);
  useEffect(() => setOrder(items), [items]);
  const dragIndex = useRef<number | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<number | null>(null);

  /** Move a row to a new index, optimistically, then persist the whole order. */
  async function move(from: number, to: number) {
    if (from === to || to < 0 || to >= order.length) return;
    const next = [...order];
    const [row] = next.splice(from, 1);
    next.splice(to, 0, row);
    setOrder(next);
    try {
      await save(next.map((x) => x.id));
    } catch (e) {
      onError(e);
    }
    // On failure too: never leave a wrong order on screen — take the
    // server's word for it.
    onSettled();
  }

  function reset() {
    dragIndex.current = null;
    setDragging(null);
    setOver(null);
  }

  /** Spread onto the draggable element for row `i`. */
  function dragProps(i: number) {
    return {
      draggable: true,
      onDragStart: (e: React.DragEvent) => {
        dragIndex.current = i;
        setDragging(i);
        e.dataTransfer.effectAllowed = "move";
      },
      onDragOver: (e: React.DragEvent) => {
        if (dragIndex.current === null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        setOver(i);
      },
      onDrop: (e: React.DragEvent) => {
        const from = dragIndex.current;
        if (from === null) return;
        e.preventDefault();
        reset();
        move(from, i);
      },
      onDragEnd: reset,
    };
  }

  /**
   * Feedback classes for row `i`: the dragged row fades, the drop target
   * shows an accent line above it (or a ring, for chips that wrap).
   */
  function dragClass(i: number, indicator: "line" | "ring" = "line") {
    const target = over === i && dragging !== null && dragging !== i;
    return [
      dragging === i ? "opacity-40" : "",
      target ? (indicator === "ring" ? "ring-2 ring-accent" : "border-t-2 border-t-accent") : "",
    ].join(" ");
  }

  return { order, move, dragProps, dragClass };
}

export type Reorder<T extends { id: number }> = ReturnType<typeof useReorder<T>>;
