/**
 * i18next configuration for Facil Mobile
 *
 * - Detects the device language via expo-localization
 * - Supports Spanish (es), French (fr), and English (en)
 * - Defaults to Spanish (official language of Equatorial Guinea)
 * - Disables React Suspense (not compatible with Expo Router out-of-the-box)
 *
 * Import this module at the app entry point to initialise translations:
 * ```ts
 * import '@core/i18n';
 * ```
 */

import 'intl-pluralrules';
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { getLocales } from 'expo-localization';

import es from './locales/es.json';
import fr from './locales/fr.json';
import en from './locales/en.json';

// ---------------------------------------------------------------------------
// Supported languages
// ---------------------------------------------------------------------------

/** Languages supported by the Facil app. */
export const SUPPORTED_LANGUAGES = ['es', 'fr', 'en'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

// ---------------------------------------------------------------------------
// System language detection
// ---------------------------------------------------------------------------

/**
 * Detect the best matching language from the device locale list.
 * Falls back to 'es' (official language of Equatorial Guinea) when the
 * system language is not among the supported set.
 */
function detectLanguage(): SupportedLanguage {
  const locales = getLocales();
  const systemCode = locales[0]?.languageCode ?? 'es';

  if ((SUPPORTED_LANGUAGES as readonly string[]).includes(systemCode)) {
    return systemCode as SupportedLanguage;
  }

  return 'es';
}

const defaultLanguage: SupportedLanguage = detectLanguage();

// ---------------------------------------------------------------------------
// i18next initialisation
// ---------------------------------------------------------------------------

i18n.use(initReactI18next).init({
  resources: {
    es: { translation: es },
    fr: { translation: fr },
    en: { translation: en },
  },
  lng: defaultLanguage,
  fallbackLng: 'es',
  interpolation: {
    // React already escapes values
    escapeValue: false,
  },
  react: {
    // Expo Router does not support React.Suspense for i18n loading
    useSuspense: false,
  },
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Change the app language at runtime.
 * Also updates the API client locale header.
 */
export async function changeLanguage(lang: SupportedLanguage): Promise<void> {
  await i18n.changeLanguage(lang);

  // Lazy import to avoid circular dependency (api/client imports config which
  // may import i18n during startup).
  const { setApiLocale } = await import('@core/api/client');
  setApiLocale(lang);
}

/**
 * Get the current active language.
 */
export function getCurrentLanguage(): SupportedLanguage {
  return (i18n.language ?? 'es') as SupportedLanguage;
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export default i18n;
export { defaultLanguage };
