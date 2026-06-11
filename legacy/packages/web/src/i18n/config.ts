/**
 * i18n configuration for TaxasGE
 * Supports ES (Spanish), FR (French), EN (English)
 */

export const locales = ['es', 'fr', 'en'] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = 'es'; // Spanish for Guinea Ecuatorial

export const localeNames: Record<Locale, string> = {
  es: 'Español',
  fr: 'Français',
  en: 'English',
};
