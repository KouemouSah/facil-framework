/**
 * Pure helpers for the JsonField editor — kept out of the "use client"
 * component so they're unit-testable without a DOM.
 */

export type JsonParseResult =
  | { value: Record<string, unknown>; valid: true; error: null }
  | { value: undefined; valid: false; error: string };

/**
 * Parse free-form text into a JSON object. Empty text === `{}` (matches the
 * backend `default_factory=dict`). Arrays and primitives are rejected because
 * the target backend fields are `dict`.
 */
export function parseJsonObject(text: string): JsonParseResult {
  const trimmed = text.trim();
  if (trimmed === "") return { value: {}, valid: true, error: null };
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { value: undefined, valid: false, error: "Invalid JSON" };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { value: undefined, valid: false, error: "Must be a JSON object" };
  }
  return { value: parsed as Record<string, unknown>, valid: true, error: null };
}

/** Pretty-print a value for display; empty/nullish objects render as "". */
export function prettyJson(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "object" && Object.keys(value as object).length === 0) return "";
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}
