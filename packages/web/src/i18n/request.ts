import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
import { getBranding } from "@/lib/server/backend";

// Supported locales (catalogues under ./messages). The deployment picks a default
// via branding.default_locale; a signed-in user overrides it with the switcher.
export const locales = ["en", "fr", "es"] as const;
export const defaultLocale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

type Locale = (typeof locales)[number];
function isLocale(v: string | undefined | null): v is Locale {
  return !!v && (locales as readonly string[]).includes(v);
}

/**
 * Locale resolution (P2.3), highest precedence first:
 *   1. `NEXT_LOCALE` cookie — the user's explicit choice (LocaleSwitcher).
 *   2. `branding.default_locale` — the deployment default (gov = fr, etc.).
 *   3. `defaultLocale` ("en") — fail-safe.
 * A cookie value outside the supported set is ignored (falls through).
 */
export default getRequestConfig(async () => {
  const jar = await cookies();
  const chosen = jar.get(LOCALE_COOKIE)?.value;

  let locale: Locale = defaultLocale;
  if (isLocale(chosen)) {
    locale = chosen;
  } else {
    const branding = await getBranding().catch(() => null);
    if (branding && isLocale(branding.default_locale)) locale = branding.default_locale;
  }

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
