/**
 * Templates Module
 * Document and procedure templates management
 *
 * @module templates
 */

// Components - Rename TemplateFilters to avoid conflict with type
export {
  TemplateCard,
  TemplateList,
  TemplateForm,
  TemplateFilters as TemplateFiltersComponent,
  ProcedureStepsList,
} from './components'

// Hooks
export * from './hooks'

// Types
export type {
  TemplateType,
  TemplateFilters,
  TemplateListProps,
  TemplateCardProps,
  TemplateFormProps,
  DocumentTemplate,
  DocumentTemplateCreate,
  DocumentTemplateUpdate,
  ProcedureTemplate,
  ProcedureTemplateCreate,
  ProcedureTemplateUpdate,
  ProcedureStep,
  ProcedureStepCreate,
  ProcedureStepUpdate,
} from './types'

// Services
export {
  documentTemplatesApi,
  procedureTemplatesApi,
  procedureStepsApi,
} from './services/api'
export { default as templatesApi } from './services/api'
