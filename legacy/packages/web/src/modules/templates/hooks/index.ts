/**
 * Templates Module Hooks
 * React Query hooks for template management
 *
 * @module templates/hooks
 */

export {
  useDocumentTemplates,
  useDocumentTemplate,
  useCreateDocumentTemplate,
  useUpdateDocumentTemplate,
  useDeleteDocumentTemplate,
} from './useDocumentTemplates'

export {
  useProcedureTemplates,
  useProcedureTemplate,
  useCreateProcedureTemplate,
  useUpdateProcedureTemplate,
  useDeleteProcedureTemplate,
  useProcedureSteps,
  useReorderProcedureSteps,
} from './useProcedureTemplates'
