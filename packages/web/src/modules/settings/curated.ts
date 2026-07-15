// Curated config keys — those with a friendlier, dedicated editor than the raw
// key/value config page. Editing them raw still works (parity), but the config
// page hints the operator toward the curated surface AND links there (Phase A5).

/** Key prefixes that have a dedicated editor elsewhere. */
export const CURATED = ["branding.", "ai.routing", "ai.providers"] as const;

export const isCurated = (key: string): boolean =>
  CURATED.some((p) => key === p || key.startsWith(p));

/**
 * Route of the dedicated editor for a curated key, or null if none.
 * - `branding.*`            → Branding editor (`/settings`)
 * - `ai.routing`/`ai.providers` → AI routing lives in the Providers page (`/providers`)
 */
export function curatedHref(key: string): string | null {
  if (key === "branding" || key.startsWith("branding.")) return "/settings";
  if (key === "ai.routing" || key === "ai.providers") return "/providers";
  return null;
}
