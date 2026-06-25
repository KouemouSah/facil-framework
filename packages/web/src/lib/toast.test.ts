import { describe, expect, it } from "vitest";
import { TOAST_LIMIT, toastReducer, type ToastItem, type ToastState } from "./toast";

const mk = (id: string): ToastItem => ({ id, title: `t-${id}`, variant: "default" });
const empty: ToastState = { toasts: [] };

describe("toastReducer", () => {
  it("adds newest-first", () => {
    const s1 = toastReducer(empty, { type: "add", toast: mk("a") });
    const s2 = toastReducer(s1, { type: "add", toast: mk("b") });
    expect(s2.toasts.map((t) => t.id)).toEqual(["b", "a"]);
  });

  it("caps at TOAST_LIMIT, dropping the oldest", () => {
    let s = empty;
    for (let i = 0; i < TOAST_LIMIT + 3; i++) {
      s = toastReducer(s, { type: "add", toast: mk(String(i)) });
    }
    expect(s.toasts).toHaveLength(TOAST_LIMIT);
    // newest first → the most recent id is at the head, oldest dropped.
    expect(s.toasts[0].id).toBe(String(TOAST_LIMIT + 2));
    expect(s.toasts.some((t) => t.id === "0")).toBe(false);
  });

  it("dismiss removes only the matching id", () => {
    let s = toastReducer(empty, { type: "add", toast: mk("a") });
    s = toastReducer(s, { type: "add", toast: mk("b") });
    s = toastReducer(s, { type: "dismiss", id: "a" });
    expect(s.toasts.map((t) => t.id)).toEqual(["b"]);
  });

  it("clear empties the queue", () => {
    let s = toastReducer(empty, { type: "add", toast: mk("a") });
    s = toastReducer(s, { type: "clear" });
    expect(s.toasts).toEqual([]);
  });

  it("ignores unknown actions (returns same state)", () => {
    const s = toastReducer(empty, { type: "noop" } as never);
    expect(s).toBe(empty);
  });
});
