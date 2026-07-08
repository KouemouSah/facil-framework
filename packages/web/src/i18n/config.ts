// Client-SAFE i18n constants (no server-only imports). Both the server config
// (`request.ts`, which pulls in `next/headers`) and client components (the
// LocaleSwitcher) import from here — a client component importing `request.ts`
// directly would drag `next/headers` into the browser bundle (build error).

export const locales = ["en", "fr", "es"] as const;
export const defaultLocale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export type Locale = (typeof locales)[number];

export function isLocale(v: string | undefined | null): v is Locale {
  return !!v && (locales as readonly string[]).includes(v);
}
