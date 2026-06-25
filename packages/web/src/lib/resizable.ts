/**
 * Pure helpers for the resizable RecordSurface panel (Phase 2). Kept framework-free
 * so the clamp/persist logic is unit-tested without a DOM; the `useResizable` hook
 * consumes these. Width is bounded [min, maxVw·viewport] and persisted per resource.
 */

export const RS_MIN_WIDTH = 360;
export const RS_MAX_VW = 0.6; // panel never wider than 60% of the viewport
export const RS_DEFAULT_WIDTH = 480;

export interface ClampOpts {
  min?: number;
  maxVw?: number;
  /** Viewport width in px (injected for testability; the hook passes innerWidth). */
  vw: number;
}

/** Clamp a desired pixel width into [min, maxVw·vw], guarding tiny viewports. */
export function clampWidth(desired: number, opts: ClampOpts): number {
  const min = opts.min ?? RS_MIN_WIDTH;
  const maxVw = opts.maxVw ?? RS_MAX_VW;
  const upper = Math.max(min, Math.round(opts.vw * maxVw));
  if (Number.isNaN(desired)) return min;
  return Math.min(upper, Math.max(min, Math.round(desired)));
}

export const widthStorageKey = (resourceKey: string): string => `rs:width:${resourceKey}`;

/** Parse a persisted width string; returns null when absent/invalid (use default). */
export function parseStoredWidth(raw: string | null): number | null {
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}
