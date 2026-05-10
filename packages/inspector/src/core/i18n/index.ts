/**
 * i18n Configuration - Facil Inspeccion
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { getLocales } from 'expo-localization';
import 'intl-pluralrules';

import { setApiLocale } from '@core/api/client';
import { appConfig } from '@core/config/app';
import { getItem, setItem } from '@core/storage/mmkv';

import es from './locales/es.json';
import fr from './locales/fr.json';
import en from './locales/en.json';

const LANGUAGE_KEY = 'inspector_preferred_language';

function getInitialLanguage(): string {
  const stored = getItem<string>(LANGUAGE_KEY);
  if (stored && appConfig.i18n.supportedLanguages.includes(stored as 'es' | 'fr' | 'en')) {
    return stored;
  }
  const deviceLang = getLocales()[0]?.languageCode ?? 'es';
  const supported = appConfig.i18n.supportedLanguages as readonly string[];
  return supported.includes(deviceLang) ? deviceLang : appConfig.i18n.defaultLanguage;
}

const initialLang = getInitialLanguage();

i18n.use(initReactI18next).init({
  resources: { es: { translation: es }, fr: { translation: fr }, en: { translation: en } },
  lng: initialLang,
  fallbackLng: 'es',
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
});

setApiLocale(initialLang);

export function changeLanguage(lang: string): void {
  if (appConfig.i18n.supportedLanguages.includes(lang as 'es' | 'fr' | 'en')) {
    i18n.changeLanguage(lang);
    setApiLocale(lang);
    setItem(LANGUAGE_KEY, lang);
  }
}

export default i18n;
