/**
 * Centralized language configuration — single source of truth.
 *
 * Used by: onboarding, profile, language picker, home page.
 */

import type { SupportedLanguage } from '@core/i18n';

export interface LanguageOption {
  code: SupportedLanguage;
  label: string;
  flag: string;
}

/** Supported languages with native labels and flag emojis. */
export const LANGUAGES: LanguageOption[] = [
  { code: 'es', label: 'Español', flag: '🇬🇶' },
  { code: 'fr', label: 'Français', flag: '🇫🇷' },
  { code: 'en', label: 'English', flag: '🇬🇧' },
];

/** Short labels for compact display (header bars, etc.) */
export const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  es: 'ES',
  fr: 'FR',
  en: 'EN',
};
