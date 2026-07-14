import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "./messages/en.json";
import fr from "./messages/fr.json";
import es from "./messages/es.json";

/**
 * Regression pin for the `sites.f.operating_hours_hint` bug (final fix
 * wave, MINORS): a hint string containing RAW, unescaped `{`/`}` (e.g. a
 * JSON example like `{"mon": ["09:00-17:00"]}`) is not valid ICU
 * MessageFormat — `next-intl`'s default `t()` throws `MALFORMED_ARGUMENT`
 * and falls back to rendering the literal key path
 * ("sites.f.operating_hours_hint") instead of the translated text.
 *
 * Verified empirically (see the task report) before fixing: `t()` on the
 * original value threw `INVALID_MESSAGE: MALFORMED_ARGUMENT`. Three sibling
 * keys under `fields.f` (`options_hint`/`relation_filter_hint`/
 * `default_hint`) had the exact same raw-brace bug and were fixed alongside
 * it — all four are pinned here, in all three locales.
 *
 * Deliberately scoped to the keys actually touched by this fix, not a
 * full-repo i18n audit: an exhaustive scan over every message in the app
 * surfaced ~80 pre-existing unrelated missing-key fallbacks, which is a
 * separate, much larger finding out of scope for this MINORS-cost fix (see
 * the task report).
 */
const FIXED_KEYS = [
  "sites.f.operating_hours_hint",
  "fields.f.options_hint",
  "fields.f.relation_filter_hint",
  "fields.f.default_hint",
];

type Messages = Record<string, unknown>;

describe.each([
  ["en", en],
  ["fr", fr],
  ["es", es],
] as const)("the four raw-JSON-brace hint keys parse as valid ICU (%s)", (locale, messages) => {
  const t = createTranslator({ locale, messages: messages as Messages });

  it.each(FIXED_KEYS)("%s does not fall back to its own literal key", (path) => {
    const rendered = t(path as never);
    expect(rendered).not.toBe(path);
    // The JSON example text must still be legible in the rendered output —
    // proves the ICU single-quote escaping didn't eat the braces.
    expect(rendered).toContain("{");
    expect(rendered).toContain("}");
  });
});
