/**
 * Global toast store — framework-mandated user feedback for mutations (CLAUDE.md).
 * The reducer is pure (unit-tested); a tiny pub/sub lets `toast()` be called from
 * anywhere (event handlers, non-React helpers) while `<Toaster>` subscribes for
 * rendering. No external state lib — keeps the bundle lean. Rendering side handles
 * `aria-live` for screen-reader announcement (a11y).
 */

export type ToastVariant = "default" | "success" | "error" | "warning";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

export interface ToastState {
  toasts: ToastItem[];
}

export type ToastAction =
  | { type: "add"; toast: ToastItem }
  | { type: "dismiss"; id: string }
  | { type: "clear" };

/** Cap visible toasts so a burst (e.g. bulk op) can't bury the screen. */
export const TOAST_LIMIT = 4;

/** Pure reducer — the unit-tested core of the store. Newest first, capped. */
export function toastReducer(state: ToastState, action: ToastAction): ToastState {
  switch (action.type) {
    case "add":
      return { toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT) };
    case "dismiss":
      return { toasts: state.toasts.filter((t) => t.id !== action.id) };
    case "clear":
      return { toasts: [] };
    default:
      return state;
  }
}

// --- Runtime store (not exercised by unit tests; the reducer above is) ---------

let state: ToastState = { toasts: [] };
const listeners = new Set<(s: ToastState) => void>();
let counter = 0;

function dispatch(action: ToastAction): void {
  state = toastReducer(state, action);
  listeners.forEach((l) => l(state));
}

export function subscribeToasts(listener: (s: ToastState) => void): () => void {
  listeners.add(listener);
  listener(state);
  return () => listeners.delete(listener);
}

export function getToastState(): ToastState {
  return state;
}

export interface ToastInput {
  title: string;
  description?: string;
  variant?: ToastVariant;
}

/** Enqueue a toast from anywhere. Returns the generated id (for manual dismiss). */
export function toast(input: ToastInput): string {
  const id = `t${++counter}`;
  dispatch({ type: "add", toast: { id, variant: "default", ...input } });
  return id;
}

export function dismissToast(id: string): void {
  dispatch({ type: "dismiss", id });
}
