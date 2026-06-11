/**
 * Translations Admin Types
 * Type definitions for translations management
 *
 * BACKEND ALIGNMENT:
 * - Entity translations: entity_translation.py (Pydantic models)
 * - System translations: translation.py (Pydantic models)
 * - Frontend translations: frontend_translation_routes.py
 *
 * @module translations/types
 */

// =============================================================================
// ENUMS - Match backend ENUMs
// =============================================================================

/**
 * Entity type enum - matches database translatable_entity_type
 * Values: ministry, sector, category, service, procedure_template, procedure_step, document_template
 */
export type TranslatableEntityType = 'ministry' | 'sector' | 'category' | 'service' | 'procedure_template' | 'procedure_step' | 'document_template'

/**
 * Language code enum - matches backend LanguageCode
 */
export type LanguageCode = 'es' | 'fr' | 'en'

/**
 * Translation source - how the translation was created
 */
export type TranslationSource = 'manual' | 'import' | 'machine' | 'review'

/**
 * Translation quality level
 */
export type TranslationQuality = 'draft' | 'reviewed' | 'approved'

// =============================================================================
// ENTITY TRANSLATIONS - entity_translations table
// =============================================================================

/**
 * Entity translation record
 * Maps to: entity_translations table
 */
export interface EntityTranslation {
  id: number
  entity_type: TranslatableEntityType
  entity_code: string
  language_code: LanguageCode
  field_name: string
  translation_text: string
  translation_source: TranslationSource
  translation_quality?: TranslationQuality
  created_at: string
  updated_at?: string
}

/**
 * Request for creating entity translation
 */
export interface EntityTranslationCreate {
  entity_type: TranslatableEntityType
  entity_code: string
  language_code: LanguageCode
  field_name: string
  translation_text: string
  translation_source?: TranslationSource
  translation_quality?: TranslationQuality
}

/**
 * Request for updating entity translation
 */
export interface EntityTranslationUpdate {
  translation_text: string
  translation_source?: TranslationSource
  translation_quality?: TranslationQuality
}

/**
 * Bulk create item - all 3 languages for one entity field
 */
export interface EntityTranslationBulkItem {
  entity_type: TranslatableEntityType
  entity_code: string
  field_name: string
  es: string
  fr: string
  en: string
  translation_source?: TranslationSource
}

/**
 * Bulk create request
 */
export interface EntityTranslationBulkCreate {
  translations: EntityTranslationBulkItem[]
}

/**
 * Search parameters for entity translations
 */
export interface EntityTranslationSearchParams {
  entity_type?: TranslatableEntityType
  entity_code?: string
  language_code?: LanguageCode
  field_name?: string
  search_term?: string
  limit?: number
  offset?: number
}

/**
 * Grouped translations for an entity (all languages)
 */
export interface EntityTranslationGrouped {
  entity_type: string
  entity_code: string
  translations: Record<string, Record<LanguageCode, string>>
}

/**
 * Entity translation statistics
 */
export interface EntityTranslationStats {
  total_translations: number
  by_entity_type: Record<string, number>
  by_language: Record<string, number>
  by_field: Record<string, number>
  distinct_entities?: Record<string, number>
}

/**
 * Paginated entity translations response
 */
export interface EntityTranslationListResponse {
  translations: EntityTranslation[]
  total: number
  limit: number
  offset: number
}

// =============================================================================
// SYSTEM TRANSLATIONS - translations table
// =============================================================================

/**
 * Enriched system category with localized labels
 * Backend returns these from GET /translations/system/categories
 */
export interface SystemCategory {
  code: string
  label: string
  description: string | null
  db_table: string | null
  db_column: string | null
  db_enum: string | null
  group: string  // Group code (enum type or functional group)
  group_label: string  // Localized group label
}

/**
 * Translation group (ENUM type or functional group)
 * Backend returns these from GET /translations/system/groups
 */
export interface TranslationGroup {
  code: string  // Group code (e.g., "user_role_enum", "ui")
  label: string  // Localized label
  type: 'enum' | 'functional'  // Group type
  table: string | null  // Associated DB table (for enum groups)
  column: string | null  // Associated DB column (for enum groups)
}

/**
 * Response from GET /translations/system/groups
 */
export interface TranslationGroupsResponse {
  groups: TranslationGroup[]
  count: number
  language: LanguageCode
}

/**
 * Response from GET /translations/system/categories
 */
export interface SystemCategoriesResponse {
  categories: SystemCategory[]
  count: number
  language: LanguageCode
}

/**
 * System translation record
 * Maps to: translations table
 * Used for: ENUMs, UI labels, forms, messages
 */
export interface SystemTranslation {
  id: number
  category: string
  key_code: string
  context?: string
  es: string
  fr: string
  en: string
  description?: string
  translation_source: TranslationSource
  created_at: string
  updated_at?: string
  created_by?: string
}

/**
 * Request for creating system translation
 */
export interface SystemTranslationCreate {
  category: string
  key_code: string
  context?: string
  es: string
  fr: string
  en: string
  description?: string
  translation_source?: TranslationSource
}

/**
 * Request for updating system translation
 */
export interface SystemTranslationUpdate {
  es?: string
  fr?: string
  en?: string
  description?: string
  translation_source?: TranslationSource
}

/**
 * Search parameters for system translations
 */
export interface SystemTranslationSearchParams {
  category?: string
  group?: string  // Filter by group (ENUM type or functional group)
  key_code?: string
  context?: string
  search_term?: string
  limit?: number
  offset?: number
}

/**
 * Paginated system translations response
 */
export interface SystemTranslationListResponse {
  translations: SystemTranslation[]
  total: number
  limit: number
  offset: number
}

// =============================================================================
// FRONTEND TRANSLATIONS - next-intl JSON sync
// =============================================================================

/**
 * Frontend translation namespace info
 */
export interface FrontendNamespace {
  name: string
  key_count: number
}

/**
 * Frontend translation stats
 */
export interface FrontendTranslationStats {
  total_keys: number
  by_namespace: Record<string, number>
  missing_translations: {
    es: number
    fr: number
    en: number
  }
  coverage: {
    es: number
    fr: number
    en: number
  }
}

/**
 * Frontend translation search params
 */
export interface FrontendTranslationSearchParams {
  namespace?: string
  key_code?: string
  search_term?: string
  limit?: number
  offset?: number
}

/**
 * Frontend translation import result
 */
export interface FrontendTranslationImportResult {
  namespace: string
  language: LanguageCode
  created: number
  updated: number
  total_processed: number
  errors: string[]
  error_count: number
}

// =============================================================================
// ENTITY TYPE OPTIONS (for UI dropdowns)
// =============================================================================

export interface EntityTypeOption {
  value: TranslatableEntityType
  label: string
  label_fr: string
  label_en: string
}

export const ENTITY_TYPE_OPTIONS: EntityTypeOption[] = [
  { value: 'ministry', label: 'Ministerios', label_fr: 'Ministères', label_en: 'Ministries' },
  { value: 'sector', label: 'Sectores', label_fr: 'Secteurs', label_en: 'Sectors' },
  { value: 'category', label: 'Categorías', label_fr: 'Catégories', label_en: 'Categories' },
  { value: 'service', label: 'Servicios Fiscales', label_fr: 'Services Fiscaux', label_en: 'Fiscal Services' },
  { value: 'procedure_template', label: 'Procedimientos', label_fr: 'Procédures', label_en: 'Procedures' },
  { value: 'procedure_step', label: 'Pasos de Procedimiento', label_fr: 'Étapes de Procédure', label_en: 'Procedure Steps' },
  { value: 'document_template', label: 'Plantillas de Documento', label_fr: 'Modèles de Document', label_en: 'Document Templates' },
]

export const LANGUAGE_OPTIONS = [
  { value: 'es' as LanguageCode, label: 'Español', flag: '🇪🇸' },
  { value: 'fr' as LanguageCode, label: 'Français', flag: '🇫🇷' },
  { value: 'en' as LanguageCode, label: 'English', flag: '🇬🇧' },
]

export const TRANSLATION_SOURCE_OPTIONS = [
  { value: 'manual' as TranslationSource, label: 'Manual' },
  { value: 'import' as TranslationSource, label: 'Importación' },
  { value: 'machine' as TranslationSource, label: 'Traducción automática' },
  { value: 'review' as TranslationSource, label: 'Revisión' },
]

export const TRANSLATION_QUALITY_OPTIONS = [
  { value: 'draft' as TranslationQuality, label: 'Borrador', color: 'yellow' },
  { value: 'reviewed' as TranslationQuality, label: 'Revisado', color: 'blue' },
  { value: 'approved' as TranslationQuality, label: 'Aprobado', color: 'green' },
]

// =============================================================================
// ENUM MANAGEMENT TYPES
// =============================================================================

/**
 * Modifiable ENUM types
 */
export type ModifiableEnumType =
  | 'user_role_enum'
  | 'declaration_status_enum'
  | 'payment_status_enum'
  | 'document_status_enum'
  | 'service_type_enum'
  | 'calculation_method_enum'

/**
 * ENUM metadata from backend
 */
export interface EnumMetadata {
  enum_name: ModifiableEnumType
  label: string
  total_values: number
  active_count: number
  archived_count: number
}

/**
 * ENUM value with translation status
 */
export interface EnumValueWithTranslation {
  value: string
  display_value: string
  is_archived: boolean
  usage_count: number
  can_archive: boolean
  has_translation: boolean
  translation_id: number | null
  es: string | null
  fr: string | null
  en: string | null
}

/**
 * Response from GET /enums/{enum_name}
 */
export interface EnumValuesResponse {
  enum_name: string
  category: string
  values: EnumValueWithTranslation[]
  total: number
  with_translation: number
  without_translation: number
}

/**
 * Request for adding a new ENUM value
 */
export interface AddEnumValueRequest {
  value: string
  es: string
  fr: string
  en: string
}

/**
 * Request for updating ENUM translation
 */
export interface UpdateEnumTranslationRequest {
  es?: string
  fr?: string
  en?: string
}

/**
 * Response from add/archive/restore operations
 */
export interface EnumOperationResponse {
  enum_name: string
  message: string
  [key: string]: unknown
}

/**
 * Untranslated ENUM value
 */
export interface UntranslatedEnumValue {
  enum_name: string
  category: string
  value: string
}

/**
 * Modifiable ENUMs list with labels
 */
export const MODIFIABLE_ENUM_OPTIONS: Array<{
  value: ModifiableEnumType
  label_es: string
  label_fr: string
  label_en: string
}> = [
  { value: 'user_role_enum', label_es: 'Roles de Usuario', label_fr: 'Rôles Utilisateur', label_en: 'User Roles' },
  { value: 'declaration_status_enum', label_es: 'Estados de Declaración', label_fr: 'Statuts de Déclaration', label_en: 'Declaration Status' },
  { value: 'payment_status_enum', label_es: 'Estados de Pago', label_fr: 'Statuts de Paiement', label_en: 'Payment Status' },
  { value: 'document_status_enum', label_es: 'Estados de Documento', label_fr: 'Statuts de Document', label_en: 'Document Status' },
  { value: 'service_type_enum', label_es: 'Tipos de Servicio', label_fr: 'Types de Service', label_en: 'Service Types' },
  { value: 'calculation_method_enum', label_es: 'Métodos de Cálculo', label_fr: 'Méthodes de Calcul', label_en: 'Calculation Methods' },
]
