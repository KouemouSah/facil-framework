/**
 * Entity URL utilities
 *
 * Deterministic bidirectional conversion between URL slugs and entity codes.
 * Convention: DB = UPPER_SNAKE_CASE, URL = lower-kebab-case.
 *
 * Some entities have DB codes in Spanish that don't match the English URL slug.
 * These are handled via explicit override maps.
 *
 * Examples:
 *   slugToEntityCode('cnedoge-pasaporte') → 'CNEDOGE_PASAPORTE'
 *   slugToEntityCode('treasury') → 'TESORO'
 *   entityCodeToSlug('CNEDOGE_PASAPORTE') → 'cnedoge-pasaporte'
 *   entityCodeToSlug('TESORO') → 'treasury'
 *
 * @module agent-dashboard/utils
 */

import type { EntityCode } from '../types';

/**
 * Override map: URL slug → DB entity code
 * For entities whose DB code doesn't follow the toUpperCase() convention.
 */
const SLUG_TO_CODE: Record<string, EntityCode> = {
  'treasury': 'TESORO' as EntityCode,
};

/**
 * Reverse override map: DB entity code → URL slug
 */
const CODE_TO_SLUG: Record<string, string> = {
  'TESORO': 'treasury',
};

/** Convert URL slug to database entity code */
export function slugToEntityCode(slug: string): EntityCode {
  const override = SLUG_TO_CODE[slug.toLowerCase()];
  if (override) return override;
  return slug.toUpperCase().replace(/-/g, '_') as EntityCode;
}

/** Convert database entity code to URL slug */
export function entityCodeToSlug(code: string): string {
  const override = CODE_TO_SLUG[code.toUpperCase()];
  if (override) return override;
  return code.toLowerCase().replace(/_/g, '-');
}
