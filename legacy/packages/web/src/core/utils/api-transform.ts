/**
 * Shared API key transformation utilities.
 * Converts between snake_case (backend) and camelCase (frontend).
 */

export function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

export function transformKeys<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => transformKeys(item)) as T
  if (typeof obj !== 'object') return obj as T
  const transformed: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    transformed[snakeToCamel(key)] = transformKeys(value)
  }
  return transformed as T
}

export function toSnakeCase<T>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map(item => toSnakeCase(item)) as T
  if (typeof obj !== 'object') return obj as T
  const transformed: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    transformed[camelToSnake(key)] = toSnakeCase(value)
  }
  return transformed as T
}
