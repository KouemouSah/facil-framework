/**
 * Formatting utilities for the Facil Mobile app
 *
 * - Currency: XAF (Central African CFA Franc) — no decimals, thousands separator
 * - Phone: Equatorial Guinea format (country code +240, prefixes 222/555/551/333)
 * - Dates: uses date-fns with locale-aware formatting
 */

import { format as fnsFormat, formatDistanceToNow, isValid } from 'date-fns';
import { es, fr, enUS } from 'date-fns/locale';

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

// `Locale` type isn't re-exported through date-fns v3 root in `bundler` resolution;
// inferring from a concrete locale gives the same shape without the broken import.
type DateFnsLocale = typeof es;

const DATE_FNS_LOCALES: Record<string, DateFnsLocale> = {
  es,
  fr,
  en: enUS,
};

/** Get the date-fns locale matching the current i18n language. */
function getDateLocale(): DateFnsLocale {
  // Lazy read to avoid circular import at module init time.
  // Falls back to Spanish if i18n is not yet initialised.
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const i18n = require('@core/i18n').default;
    return DATE_FNS_LOCALES[i18n.language] ?? es;
  } catch {
    return es;
  }
}

/** Normalise a date input to a Date object. */
function toDate(date: string | Date): Date {
  if (typeof date === 'string') {
    // `new Date(iso)` parses ISO 8601 reliably across RN runtimes; date-fns parseISO
    // isn't re-exported via the bundler resolution path in v3.
    const parsed = new Date(date);
    return isValid(parsed) ? parsed : new Date(NaN);
  }
  return date;
}

// ---------------------------------------------------------------------------
// Currency
// ---------------------------------------------------------------------------

/**
 * Format an amount in XAF (Central African CFA Franc).
 *
 * XAF has no decimal sub-unit, so decimals are always omitted.
 * Uses non-breaking space as thousands separator for readability.
 *
 * @example
 * formatCurrency(150000)       // "150 000 XAF"
 * formatCurrency(150000, 'XAF') // "150 000 XAF"
 * formatCurrency(0)            // "0 XAF"
 */
export function formatCurrency(amount: number, currency = 'XAF'): string {
  const rounded = Math.round(amount);
  // Format with thousands separator (space for XAF per CEMAC convention)
  const formatted = rounded
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0'); // non-breaking space
  return `${formatted} ${currency}`;
}

// ---------------------------------------------------------------------------
// Dates
// ---------------------------------------------------------------------------

/**
 * Format a date string or Date object.
 *
 * @param date   - ISO 8601 string or Date object
 * @param pattern - date-fns format pattern (default: 'dd/MM/yyyy')
 *
 * @example
 * formatDate('2026-03-24T10:30:00Z')         // "24/03/2026"
 * formatDate('2026-03-24T10:30:00Z', 'PPp')  // "24 mar 2026, 10:30" (locale-aware)
 */
export function formatDate(date: string | Date, pattern = 'dd/MM/yyyy'): string {
  try {
    return fnsFormat(toDate(date), pattern, { locale: getDateLocale() });
  } catch {
    return String(date);
  }
}

/**
 * Format a date as a relative time string (e.g. "hace 3 horas", "il y a 2 jours").
 *
 * @example
 * formatRelativeTime('2026-03-24T08:00:00Z') // "hace 2 horas"
 */
export function formatRelativeTime(date: string | Date): string {
  try {
    // date-fns v3 ships `.d.mts` only for ./types.js, so under `moduleResolution: bundler`
    // the `locale` field on FormatDistanceOptions resolves empty. Cast to bypass.
    return formatDistanceToNow(toDate(date), {
      addSuffix: true,
      locale: getDateLocale(),
    } as Parameters<typeof formatDistanceToNow>[1]);
  } catch {
    return String(date);
  }
}

// ---------------------------------------------------------------------------
// Phone numbers
// ---------------------------------------------------------------------------

/**
 * Format a phone number for Equatorial Guinea display.
 *
 * Equatorial Guinea numbers:
 * - Country code: +240
 * - Landline prefixes: 333 (Malabo), 222 (Bata) — 9 digits total
 * - Mobile prefixes: 222, 551, 555 — 9 digits total
 *
 * @example
 * formatPhoneNumber('222123456')    // "+240 222 123 456"
 * formatPhoneNumber('+240555678901') // "+240 555 678 901"
 * formatPhoneNumber('333123456')    // "+240 333 123 456"
 */
export function formatPhoneNumber(phone: string): string {
  // Strip all non-digits
  const digits = phone.replace(/\D/g, '');

  // Remove country code if present
  const local = digits.startsWith('240') ? digits.slice(3) : digits;

  if (local.length === 9) {
    // Standard GE format: XXX XXX XXX
    return `+240 ${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`;
  }

  if (local.length === 6) {
    // Short local number (older format): XXX XXX
    return `+240 ${local.slice(0, 3)} ${local.slice(3)}`;
  }

  // Unknown length — return with country code prefix, no formatting
  return `+240 ${local}`;
}

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

/**
 * Truncate text to a maximum length, appending ellipsis if truncated.
 *
 * @example
 * truncateText('Hello World', 5) // "Hello..."
 * truncateText('Hi', 5)          // "Hi"
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}
