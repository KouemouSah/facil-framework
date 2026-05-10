/**
 * Convert a SQL LIKE pattern to a JavaScript RegExp.
 * - `%` → `.*` (match any characters)
 * - `_` → `.`  (match single character)
 * - All other regex special chars are escaped.
 *
 * @example sqlLikeToRegex('PASAPORTE_%').test('PASAPORTE_ORDINARIO') // true
 */
export function sqlLikeToRegex(pattern: string): RegExp {
  let regexStr = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  regexStr = regexStr.replace(/%/g, '.*');
  regexStr = regexStr.replace(/_/g, '.');
  return new RegExp(`^${regexStr}$`, 'i');
}
