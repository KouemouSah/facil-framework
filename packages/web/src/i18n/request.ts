import { getRequestConfig } from "next-intl/server";

// Supported locales come from backend branding.supported_locales (en/fr/es).
// D5.0 ships a single resolved locale; locale routing/switching lands in D5.1.
export const locales = ["en", "fr", "es"] as const;
export const defaultLocale = "en";

export default getRequestConfig(async () => {
  const locale = defaultLocale;
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
