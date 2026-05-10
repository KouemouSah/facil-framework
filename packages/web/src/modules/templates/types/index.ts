/**
 * Templates Module Types
 * Re-exports from fiscal-service types + module-specific types
 *
 * @module templates/types
 */

// Re-export template types from fiscal-service
export type {
  DocumentTemplate,
  DocumentTemplateCreate,
  DocumentTemplateUpdate,
  ProcedureTemplate,
  ProcedureTemplateCreate,
  ProcedureTemplateUpdate,
  ProcedureStep,
  ProcedureStepCreate,
  ProcedureStepUpdate,
} from '@/types/fiscal-service'

// Module-specific types
export type TemplateType = 'document' | 'procedure'

export interface TemplateFilters {
  category?: string
  isActive?: boolean
  type?: TemplateType
  search?: string
}

export interface TemplateListProps {
  type: TemplateType
  filters?: TemplateFilters
  onSelect?: (id: string | number) => void
}

export interface TemplateCardProps {
  id: string | number
  name: string
  description?: string
  category?: string
  isActive: boolean
  type: TemplateType
  onClick?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

export interface TemplateFormProps {
  type: TemplateType
  initialData?: any
  onSubmit: (data: any) => Promise<void>
  onCancel: () => void
  isLoading?: boolean
}
