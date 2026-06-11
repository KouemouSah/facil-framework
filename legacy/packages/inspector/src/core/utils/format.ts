/**
 * Formatting Utilities - Facil Inspeccion
 */

import { format, parseISO, isValid, type Locale } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';

const localeMap: Record<string, Locale> = { es, fr, en: enUS } as Record<string, Locale>;

export function formatCurrency(amount: number, currency = 'XAF'): string {
  return new Intl.NumberFormat('es-GQ', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(
  dateString: string | Date,
  formatStr = 'dd/MM/yyyy',
  locale = 'es',
): string {
  try {
    const date = typeof dateString === 'string' ? parseISO(dateString) : dateString;
    if (!isValid(date)) return '-';
    return format(date, formatStr, { locale: localeMap[locale] ?? es });
  } catch {
    return '-';
  }
}

export function formatDateTime(dateString: string, locale = 'es'): string {
  return formatDate(dateString, 'dd/MM/yyyy HH:mm', locale);
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('es-GQ').format(num);
}
