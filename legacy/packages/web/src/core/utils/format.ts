/**
 * Formatting Utilities
 * Common formatting functions for dates, currency, etc.
 */

import { format, parseISO } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';
import { APP_CONSTANTS } from '@/core/config/constants';

/**
 * Get date-fns locale from language code
 */
function getLocale(language: string) {
  const locales = {
    es: es,
    fr: fr,
    en: enUS,
  };
  return locales[language as keyof typeof locales] || es;
}

/**
 * Format date string to localized format
 */
export function formatDate(
  date: string | Date,
  formatStr: string = APP_CONSTANTS.DATE_FORMATS.SHORT,
  language: string = 'es'
): string {
  try {
    const dateObj = typeof date === 'string' ? parseISO(date) : date;
    return format(dateObj, formatStr, { locale: getLocale(language) });
  } catch (error) {
    console.error('Error formatting date:', error);
    return String(date);
  }
}

/**
 * Format currency (XAF - Central African Franc)
 */
export function formatCurrency(amount: number, language: string = 'es'): string {
  if (amount === 0) {
    return language === 'fr' ? 'Gratuit' : 'Gratis';
  }

  return new Intl.NumberFormat(language === 'fr' ? 'fr-FR' : 'es-ES', {
    style: 'currency',
    currency: 'XAF',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format amount in XAF (Franc CFA) with locale-aware decimal separator.
 * Accepts number or string (from backend Decimal). Used by service-bundles.
 */
export function formatXAF(amount: number | string, locale: string = 'es'): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  if (isNaN(num)) return '0 XAF'
  const intlLocale = locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ'
  return new Intl.NumberFormat(intlLocale, { style: 'decimal', maximumFractionDigits: 0 }).format(num) + ' XAF'
}

/**
 * Format number with thousands separator
 */
export function formatNumber(value: number, language: string = 'es'): string {
  return new Intl.NumberFormat(language === 'fr' ? 'fr-FR' : 'es-ES').format(value);
}

/**
 * Format file size in human-readable format
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Truncate text to specified length
 */
export function truncate(text: string, length: number = 100): string {
  if (text.length <= length) return text;
  return text.substring(0, length).trim() + '...';
}

/**
 * Capitalize first letter of string
 */
export function capitalize(text: string): string {
  if (!text) return '';
  return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
}

/**
 * Get initials from name
 */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((part) => part.charAt(0).toUpperCase())
    .join('')
    .substring(0, 2);
}
