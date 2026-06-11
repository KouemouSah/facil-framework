/**
 * i18n Helper Utilities
 *
 * Locale-aware field selection for database entities that have
 * language-specific columns (name_es, name_fr, name_en).
 *
 * Used when the backend returns entities with _es/_fr/_en suffixed fields
 * and the frontend needs to display the correct language based on locale.
 */

type SupportedLocale = 'es' | 'fr' | 'en';

/**
 * Get a localized field from an entity that has _es/_fr/_en suffixed columns.
 *
 * Tries the requested locale first, falls back to Spanish (_es).
 *
 * @param entity - The entity object (e.g., { name_es: "...", name_fr: "...", name_en: "..." })
 * @param field - The base field name without suffix (e.g., "name", "description")
 * @param locale - The target locale (es, fr, en)
 * @returns The localized string, or empty string if not found
 *
 * @example
 * getLocalizedField(ministry, 'name', 'fr') // returns ministry.name_fr || ministry.name_es
 * getLocalizedField(service, 'description', 'en') // returns service.description_en || service.description_es
 */
export function getLocalizedField(
  entity: Record<string, unknown> | null | undefined,
  field: string,
  locale: string,
): string {
  if (!entity) return '';

  const lang = (['es', 'fr', 'en'].includes(locale) ? locale : 'es') as SupportedLocale;

  // Try exact locale field: name_fr, description_en, etc.
  const localizedKey = `${field}_${lang}`;
  if (entity[localizedKey] && typeof entity[localizedKey] === 'string') {
    return entity[localizedKey] as string;
  }

  // Try camelCase variant: nameFr, descriptionEn, etc.
  const camelKey = `${field}${lang.charAt(0).toUpperCase()}${lang.slice(1)}`;
  if (entity[camelKey] && typeof entity[camelKey] === 'string') {
    return entity[camelKey] as string;
  }

  // Fallback to Spanish
  const esKey = `${field}_es`;
  if (entity[esKey] && typeof entity[esKey] === 'string') {
    return entity[esKey] as string;
  }

  // CamelCase Spanish fallback: nameEs
  const esCamelKey = `${field}Es`;
  if (entity[esCamelKey] && typeof entity[esCamelKey] === 'string') {
    return entity[esCamelKey] as string;
  }

  // Try the raw field name (some APIs return just "name" already translated)
  if (entity[field] && typeof entity[field] === 'string') {
    return entity[field] as string;
  }

  return '';
}

/**
 * Shortcut for getLocalizedField with field='name'.
 */
export function getLocalizedName(
  entity: Record<string, unknown> | null | undefined,
  locale: string,
): string {
  return getLocalizedField(entity, 'name', locale);
}

/**
 * Shortcut for getLocalizedField with field='description'.
 */
export function getLocalizedDescription(
  entity: Record<string, unknown> | null | undefined,
  locale: string,
): string {
  return getLocalizedField(entity, 'description', locale);
}
