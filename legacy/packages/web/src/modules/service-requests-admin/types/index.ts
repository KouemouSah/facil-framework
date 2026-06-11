/**
 * Service Requests Admin Types
 * TypeScript types aligned with backend Pydantic models (admin_routes.py)
 *
 * @module service-requests-admin/types
 * @author Claude Code
 * @date 2025-12-28
 */

// ============================================================================
// ENUMS
// ============================================================================

export type WorkflowType = 'standard' | 'direct_payment' | 'multi_phase'

export type DocumentConditionType =
  | 'always'
  | 'age_less_than'
  | 'age_greater_than'
  | 'is_renewal'
  | 'is_new'
  | 'is_duplicate'
  | 'has_previous'
  | 'is_minor'
  | 'is_adult'
  | 'is_foreign'
  | 'is_national'
  | 'custom'

export type TariffType = 'FIXED' | 'PERCENTAGE' | 'NOTA_INGRESO'

export type AppointmentPriority = 'URGENT' | 'HIGH' | 'NORMAL' | 'LOW'

// ============================================================================
// WORKFLOW TYPES
// ============================================================================

export type WorkflowSourceType = 'predefined' | 'dynamic'

export interface Workflow {
  code: string
  name_es: string
  description_es?: string | null
  category: string
  entity_code: string
  workflow_type: WorkflowType
  requires_agent_validation: boolean
  requires_appointment: boolean
  is_generic: boolean
  appointment_delay_days?: number | null
  appointment_entity_code?: string | null
  sla_hours: number
  max_processing_days?: number | null
  display_order: number
  icon?: string | null
  color?: string | null
  config?: Record<string, unknown> | null
  is_active: boolean
  // Hierarchical grouping fields (migration 049)
  parent_workflow_code?: string | null
  tags?: string[]
  is_parent?: boolean
  // Computed fields
  documents_count?: number | null
  tariffs_count?: number | null
  source_type?: WorkflowSourceType
}

export interface WorkflowCreate {
  code: string
  name_es: string
  description_es?: string | null
  category: string
  entity_code: string
  workflow_type?: WorkflowType
  requires_agent_validation?: boolean
  requires_appointment?: boolean
  is_generic?: boolean
  appointment_delay_days?: number | null
  appointment_entity_code?: string | null
  sla_hours?: number
  max_processing_days?: number | null
  display_order?: number
  icon?: string | null
  color?: string | null
  config?: Record<string, unknown>
  is_active?: boolean
  // Hierarchical grouping fields (migration 049)
  parent_workflow_code?: string | null
  tags?: string[]
  is_parent?: boolean
}

export interface WorkflowUpdate {
  name_es?: string
  description_es?: string | null
  workflow_type?: WorkflowType
  requires_agent_validation?: boolean
  requires_appointment?: boolean
  appointment_delay_days?: number | null
  appointment_entity_code?: string | null
  sla_hours?: number
  max_processing_days?: number | null
  display_order?: number
  icon?: string | null
  color?: string | null
  config?: Record<string, unknown>
  is_active?: boolean
  // Hierarchical grouping fields (migration 049)
  parent_workflow_code?: string | null
  tags?: string[]
  is_parent?: boolean
}

export interface WorkflowFilters {
  category?: string
  entity_code?: string
  is_active?: boolean
  is_generic?: boolean
  parent_workflow_code?: string
  is_parent?: boolean
  [key: string]: string | number | boolean | undefined
}

// ============================================================================
// DOCUMENT REQUIREMENT TYPES
// ============================================================================

export interface DocumentRequirement {
  id: string
  workflow_code: string
  document_code: string
  document_name_es: string
  document_template_id?: number | null
  condition_type: string
  condition_value?: Record<string, unknown> | null
  is_required: boolean
  display_order: number
  instructions_es?: string | null
  extraction_schema_key?: string | null
  is_active: boolean
}

export interface DocumentRequirementCreate {
  document_code: string
  document_name_es: string
  document_template_id?: number | null
  condition_type?: DocumentConditionType
  condition_value?: Record<string, unknown>
  is_required?: boolean
  display_order?: number
  instructions_es?: string | null
  extraction_schema_key?: string | null
  is_active?: boolean
}

export interface DocumentRequirementUpdate {
  document_name_es?: string
  document_template_id?: number | null
  condition_type?: DocumentConditionType
  condition_value?: Record<string, unknown>
  is_required?: boolean
  display_order?: number
  instructions_es?: string | null
  extraction_schema_key?: string | null
  is_active?: boolean
}

export interface DocumentReorderItem {
  document_code: string
  display_order: number
}

// ============================================================================
// TARIFF TYPES
// ============================================================================

export interface WorkflowTariff {
  id: number
  workflow_code: string
  solicitud_type: string
  tariff_type: string
  amount: number
  percentage_rate?: number | null
  currency: string
  legal_reference?: string | null
  effective_from: string
  effective_to?: string | null
  is_active: boolean
}

export interface WorkflowTariffCreate {
  workflow_code: string
  solicitud_type?: string
  tariff_type?: TariffType
  amount: number
  percentage_rate?: number | null
  currency?: string
  legal_reference?: string | null
  effective_from: string
  effective_to?: string | null
  is_active?: boolean
}

export interface WorkflowTariffUpdate {
  solicitud_type?: string
  tariff_type?: TariffType
  amount?: number
  percentage_rate?: number | null
  currency?: string
  legal_reference?: string | null
  effective_to?: string | null
  is_active?: boolean
}

export interface TariffFilters {
  workflow_code?: string
  is_active?: boolean
  [key: string]: string | number | boolean | undefined
}

// ============================================================================
// TARIFF SUPPLEMENT TYPES
// ============================================================================

export interface TariffSupplement {
  id: number
  code: string
  name_es: string
  amount: number
  currency: string
  legal_reference?: string | null
  effective_from: string
  effective_to?: string | null
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface TariffSupplementCreate {
  code: string
  name_es: string
  amount: number
  currency?: string
  legal_reference?: string | null
  effective_from?: string | null
  effective_to?: string | null
  is_active?: boolean
}

export interface TariffSupplementUpdate {
  name_es?: string
  amount?: number
  currency?: string
  legal_reference?: string | null
  effective_from?: string | null
  effective_to?: string | null
  is_active?: boolean
}

export interface WorkflowSupplementConfig {
  id: number
  workflow_code: string
  supplement_code: string
  supplement_name?: string | null
  supplement_amount?: number | null
  quantity_per_request: number
  is_required: boolean
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface WorkflowSupplementConfigCreate {
  supplement_code: string
  quantity_per_request?: number
  is_required?: boolean
  is_active?: boolean
}

export interface WorkflowSupplementConfigUpdate {
  quantity_per_request?: number
  is_required?: boolean
  is_active?: boolean
}

// ============================================================================
// APPOINTMENT TYPES
// ============================================================================

export interface AppointmentSlotConfig {
  id: string
  entity_code: string
  entity_location_id: string
  day_of_week: number
  start_time: string
  end_time: string
  slot_duration_minutes: number
  max_appointments_per_slot: number
  is_active: boolean
  // Joined from entity_locations table
  location_name?: string | null
  location_address?: string | null
  city?: string | null
  region?: string | null
}

export interface AppointmentSlotConfigCreate {
  entity_location_id: string  // FK to entity_locations - entity_code is resolved on backend
  day_of_week: number
  start_time: string
  end_time: string
  slot_duration_minutes?: number
  max_appointments_per_slot?: number
  is_active?: boolean
}

export interface AppointmentSlotConfigBatchCreate {
  entity_location_id: string  // FK to entity_locations - entity_code is resolved on backend
  days_of_week: number[]  // Multiple days in one request
  start_time: string
  end_time: string
  slot_duration_minutes?: number
  max_appointments_per_slot?: number
  is_active?: boolean
}

export interface AppointmentSlotConfigBatchResponse {
  created: AppointmentSlotConfig[]
  skipped: { day_of_week: number; reason: string }[]
  total_created: number
  total_skipped: number
}

export interface AppointmentSlotConfigUpdate {
  entity_location_id?: string
  day_of_week?: number
  start_time?: string
  end_time?: string
  slot_duration_minutes?: number
  max_appointments_per_slot?: number
  is_active?: boolean
}

export interface AppointmentSlotConfigGroupUpdate {
  slot_ids: string[]
  entity_location_id: string
  days_of_week: number[]
  start_time: string
  end_time: string
  slot_duration_minutes: number
  max_appointments_per_slot: number
  is_active: boolean
}

export interface AppointmentSlotConfigGroupUpdateResponse {
  slots: AppointmentSlotConfig[]
  total_updated: number
  total_created: number
  total_deleted: number
}

export interface SlotConfigFilters {
  entity_code?: string
  city?: string  // Filter by city (Malabo or Bata)
  is_active?: boolean
  [key: string]: string | number | boolean | undefined
}

export interface AppointmentBlockedDate {
  id: string
  entity_code?: string | null
  blocked_date: string
  reason?: string | null
  is_recurring: boolean
}

export interface AppointmentBlockedDateCreate {
  entity_code?: string | null
  blocked_date: string
  reason?: string | null
  is_recurring?: boolean
}

export interface AppointmentBlockedDateUpdate {
  reason?: string | null
  is_recurring?: boolean
}

export interface BlockedDateFilters {
  entity_code?: string
  from_date?: string
  to_date?: string
  [key: string]: string | number | boolean | undefined
}

export interface AppointmentDelayRule {
  id: string
  workflow_code?: string | null
  priority: string
  delay_business_days: number
  is_active: boolean
}

export interface AppointmentDelayRuleCreate {
  workflow_code?: string | null
  priority: AppointmentPriority
  delay_business_days?: number
  is_active?: boolean
}

export interface AppointmentDelayRuleUpdate {
  delay_business_days?: number
  is_active?: boolean
}

// ============================================================================
// UI STATE TYPES
// ============================================================================

export interface WorkflowsAdminState {
  workflows: Workflow[]
  currentWorkflow: Workflow | null
  documents: DocumentRequirement[]
  tariffs: WorkflowTariff[]
  isLoading: boolean
  error: string | null
}

export interface AppointmentsAdminState {
  slotConfigs: AppointmentSlotConfig[]
  blockedDates: AppointmentBlockedDate[]
  delayRules: AppointmentDelayRule[]
  isLoading: boolean
  error: string | null
}

// ============================================================================
// HELPER CONSTANTS
// ============================================================================

// Database values (UPPERCASE) with display labels - must match backend workflow.category values
export const WORKFLOW_CATEGORIES_MAP: { value: string; label: string }[] = [
  { value: 'IDENTIDAD', label: 'Identidad' },
  { value: 'VEHICULOS', label: 'Vehículos' },
  { value: 'CONTRATOS', label: 'Contratos' },
  { value: 'CONDUCCION', label: 'Conducción' },
  { value: 'FUNCION_PUBLICA', label: 'Función Pública' },
  { value: 'EXTRANJERIA', label: 'Extranjería' },
  { value: 'REGISTRO_CIVIL', label: 'Registro Civil' },
  { value: 'COMERCIO', label: 'Comercio' },
  { value: 'OTROS', label: 'Otros' },
]

// Keep the old constant for backwards compatibility (use the values from the map)
export const WORKFLOW_CATEGORIES = WORKFLOW_CATEGORIES_MAP.map(c => c.value)

export const WORKFLOW_TYPES: { value: WorkflowType; label: string }[] = [
  { value: 'standard', label: 'Estándar (con validación)' },
  { value: 'direct_payment', label: 'Pago Directo (sin validación)' },
  { value: 'multi_phase', label: 'Multi-fase (Nota de Ingreso)' },
]

export const DOCUMENT_CONDITION_TYPES: { value: DocumentConditionType; label: string }[] = [
  { value: 'always', label: 'Siempre requerido' },
  { value: 'is_renewal', label: 'Si es renovación' },
  { value: 'is_new', label: 'Si es nueva solicitud' },
  { value: 'is_duplicate', label: 'Si es duplicado' },
  { value: 'has_previous', label: 'Si tiene documento anterior' },
  { value: 'is_minor', label: 'Si es menor de edad' },
  { value: 'is_adult', label: 'Si es mayor de edad' },
  { value: 'is_foreign', label: 'Si es extranjero' },
  { value: 'is_national', label: 'Si es nacional' },
  { value: 'age_less_than', label: 'Si edad menor que...' },
  { value: 'age_greater_than', label: 'Si edad mayor que...' },
  { value: 'custom', label: 'Condición personalizada' },
]

export const TARIFF_TYPES: { value: TariffType; label: string }[] = [
  { value: 'FIXED', label: 'Monto Fijo' },
  { value: 'PERCENTAGE', label: 'Porcentaje' },
  { value: 'NOTA_INGRESO', label: 'Nota de Ingreso' },
]

export const DAY_OF_WEEK_LABELS: Record<number, string> = {
  0: 'Lunes',
  1: 'Martes',
  2: 'Miércoles',
  3: 'Jueves',
  4: 'Viernes',
  5: 'Sábado',
  6: 'Domingo',
}

export const PRIORITY_LABELS: Record<AppointmentPriority, string> = {
  URGENT: 'Urgente',
  HIGH: 'Alta',
  NORMAL: 'Normal',
  LOW: 'Baja',
}
