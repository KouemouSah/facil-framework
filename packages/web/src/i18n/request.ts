import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";
import { getBranding } from "@/lib/server/backend";
import { defaultLocale, isLocale, LOCALE_COOKIE, type Locale } from "./config";

// Re-export the client-safe constants so existing importers keep working.
export { locales, defaultLocale, LOCALE_COOKIE } from "./config";

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
