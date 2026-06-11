/**
 * useImageZoom - Shared hook for Ctrl+Wheel zoom on image containers
 *
 * Attaches a native wheel event listener with { passive: false }
 * to allow preventDefault() (React's onWheel is passive by default).
 *
 * @module agent-dashboard/hooks
 * @date 2026-03-08
 */

import { useState, useRef, useCallback, useEffect } from 'react';

interface UseImageZoomOptions {
  /** Minimum zoom level (default 0.25) */
  min?: number;
  /** Maximum zoom level (default 5) */
  max?: number;
  /** Zoom step for button clicks (default 0.25) */
  step?: number;
  /** Zoom step for wheel events (default 0.15) */
  wheelStep?: number;
  /** Dependency that triggers re-attaching the listener (e.g. open state) */
  enabled?: boolean;
}

export function useImageZoom(options: UseImageZoomOptions = {}) {
  const { min = 0.25, max = 5, step = 0.25, wheelStep = 0.15, enabled = true } = options;

  const [zoomLevel, setZoomLevel] = useState(1);
  const containerRef = useRef<HTMLDivElement>(null);

  const zoomIn = useCallback(() => setZoomLevel((z) => Math.min(z + step, max)), [step, max]);
  const zoomOut = useCallback(() => setZoomLevel((z) => Math.max(z - step, min)), [step, min]);
  const zoomReset = useCallback(() => setZoomLevel(1), []);

  // Native wheel listener with { passive: false }
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !enabled) return;
    const handler = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        setZoomLevel((z) => {
          const delta = e.deltaY > 0 ? -wheelStep : wheelStep;
          return Math.min(Math.max(z + delta, min), max);
        });
      }
    };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, [enabled, min, max, wheelStep]);

  return {
    zoomLevel,
    setZoomLevel,
    containerRef,
    zoomIn,
    zoomOut,
    zoomReset,
  };
}
