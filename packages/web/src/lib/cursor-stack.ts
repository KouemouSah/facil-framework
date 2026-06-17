/**
 * Pure forward-cursor pagination stack (keyset Prev/Next) — scale 1M+ P3.
 *
 * Keyset pagination is forward-only on the server (each page returns the cursor
 * of its last row, or null on the last page). "Previous" is reconstructed on the
 * client by remembering the cursor of each page we came from. This module is the
 * pure state machine for that, so it is unit-testable without React/DOM.
 *
 *   cursor — the cursor used to fetch the CURRENT page (null = the first page).
 *   stack  — the cursors of the pages BEFORE the current one (for going back).
 */
export interface PageStack {
  cursor: string | null;
  stack: (string | null)[];
}

/** First page: no cursor, nothing to go back to. Also the reset state used on
 * any sort/filter/search/page-size change (the cursor is only valid for the
 * query it was computed against). */
export const initialPageStack: PageStack = { cursor: null, stack: [] };

/** Advance one page: remember the current cursor, adopt the server's next_cursor. */
export function pushPage(state: PageStack, nextCursor: string): PageStack {
  return { cursor: nextCursor, stack: [...state.stack, state.cursor] };
}

/** Go back one page (pop the previous cursor). No-op on the first page. */
export function popPage(state: PageStack): PageStack {
  if (state.stack.length === 0) return state;
  return {
    cursor: state.stack[state.stack.length - 1] ?? null,
    stack: state.stack.slice(0, -1),
  };
}

/** Whether a "previous" page exists (we are not on page 1). */
export const hasPrev = (state: PageStack): boolean => state.stack.length > 0;
