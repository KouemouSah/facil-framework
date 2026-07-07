/**
 * Pure gate for the destructive-confirmation dialog (audit 3). Kept out of the
 * component so it is unit-testable in the node vitest setup (no DOM). The DOM
 * `ConfirmDialog` wires this to an input; the component itself is Playwright-tested.
 */

/** Whether the confirm button may be enabled. With no `required` phrase it is
 *  always enabled; with one (high-impact deletes), the typed value must match it
 *  exactly (both trimmed, case-sensitive) — deliberate friction against mistakes. */
export function confirmTextMatches(required: string | undefined, typed: string): boolean {
  if (!required) return true;
  return typed.trim() === required.trim();
}
