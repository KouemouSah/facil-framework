"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { RS_DEFAULT_WIDTH, clampWidth, parseStoredWidth, widthStorageKey } from "@/lib/resizable";

interface ResizableOpts {
  min?: number;
  maxVw?: number;
}

/**
 * Drives a right-docked resizable panel (RecordSurface). The clamp/persist/key
 * logic is pure and unit-tested in `lib/resizable.ts`; this hook wires it to the
 * DOM (pointer drag, localStorage, viewport width). Panel sits on the right edge,
 * so dragging the handle LEFT widens it. SSR-safe: window/localStorage are only
 * read inside effects/handlers, never at module load.
 */
export function useResizable(resourceKey: string, opts: ResizableOpts = {}) {
  const [width, setWidth] = useState(RS_DEFAULT_WIDTH);
  const [isDragging, setIsDragging] = useState(false);
  const widthRef = useRef(width);
  widthRef.current = width;
  const optsRef = useRef(opts);
  optsRef.current = opts;

  // Restore persisted width on mount (clamped to the current viewport).
  useEffect(() => {
    const stored = parseStoredWidth(window.localStorage.getItem(widthStorageKey(resourceKey)));
    setWidth(clampWidth(stored ?? RS_DEFAULT_WIDTH, { vw: window.innerWidth, ...optsRef.current }));
  }, [resourceKey]);

  const onDragStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      setIsDragging(true);
      const startX = e.clientX;
      const startW = widthRef.current;

      const onMove = (ev: PointerEvent) => {
        const delta = startX - ev.clientX; // docked right → drag left widens
        setWidth(clampWidth(startW + delta, { vw: window.innerWidth, ...optsRef.current }));
      };
      const onUp = () => {
        setIsDragging(false);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        window.localStorage.setItem(widthStorageKey(resourceKey), String(widthRef.current));
      };
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    },
    [resourceKey],
  );

  return { width, onDragStart, isDragging };
}
