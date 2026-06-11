/**
 * Service Requests Admin Hooks
 * React Query hooks for workflows, documents, tariffs, and appointments
 *
 * @module service-requests-admin/hooks
 * @author Claude Code
 * @date 2025-12-28
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import {
  workflowsApi,
  documentsApi,
  tariffsApi,
  supplementsApi,
  workflowSupplementsApi,
  slotConfigsApi,
  blockedDatesApi,
  delayRulesApi,
  extractionSchemasApi,
} from '../services/api'
import type {
  WorkflowFilters,
  WorkflowCreate,
  WorkflowUpdate,
  DocumentRequirementCreate,
  DocumentRequirementUpdate,
  DocumentReorderItem,
  TariffFilters,
  WorkflowTariffCreate,
  WorkflowTariffUpdate,
  TariffSupplementCreate,
  TariffSupplementUpdate,
  WorkflowSupplementConfigCreate,
  WorkflowSupplementConfigUpdate,
  SlotConfigFilters,
  AppointmentSlotConfigCreate,
  AppointmentSlotConfigUpdate,
  AppointmentSlotConfigBatchCreate,
  AppointmentSlotConfigGroupUpdate,
  BlockedDateFilters,
  AppointmentBlockedDateCreate,
  AppointmentBlockedDateUpdate,
  AppointmentDelayRuleCreate,
  AppointmentDelayRuleUpdate,
} from '../types'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const queryKeys = {
  workflows: {
    all: ['admin', 'service-requests', 'workflows'] as const,
    list: (filters?: WorkflowFilters) => [...queryKeys.workflows.all, 'list', filters] as const,
    detail: (code: string) => [...queryKeys.workflows.all, 'detail', code] as const,
  },
  documents: {
    all: ['admin', 'service-requests', 'documents'] as const,
    byWorkflow: (workflowCode: string) => [...queryKeys.documents.all, workflowCode] as const,
  },
  tariffs: {
    all: ['admin', 'service-requests', 'tariffs'] as const,
    list: (filters?: TariffFilters) => [...queryKeys.tariffs.all, 'list', filters] as const,
  },
  supplements: {
    all: ['admin', 'service-requests', 'supplements'] as const,
    list: (activeOnly?: boolean) => [...queryKeys.supplements.all, 'list', activeOnly] as const,
    detail: (code: string) => [...queryKeys.supplements.all, 'detail', code] as const,
  },
  workflowSupplements: {
    all: ['admin', 'service-requests', 'workflow-supplements'] as const,
    byWorkflow: (workflowCode: string) => [...queryKeys.workflowSupplements.all, workflowCode] as const,
  },
  appointments: {
    slotConfigs: {
      all: ['admin', 'service-requests', 'slot-configs'] as const,
      list: (filters?: SlotConfigFilters) => ['admin', 'service-requests', 'slot-configs', 'list', filters] as const,
    },
    blockedDates: {
      all: ['admin', 'service-requests', 'blocked-dates'] as const,
      list: (filters?: BlockedDateFilters) => ['admin', 'service-requests', 'blocked-dates', 'list', filters] as const,
    },
    delayRules: {
      all: ['admin', 'service-requests', 'delay-rules'] as const,
      list: (workflowCode?: string) => ['admin', 'service-requests', 'delay-rules', 'list', workflowCode] as const,
    },
  },
  extractionSchemas: {
    all: ['admin', 'service-requests', 'extraction-schemas'] as const,
  },
}

// =============================================================================
// WORKFLOWS HOOKS
// =============================================================================

export function useWorkflows(filters?: WorkflowFilters) {
  return useQuery({
    queryKey: queryKeys.workflows.list(filters),
    queryFn: () => workflowsApi.getAll(filters),
  })
}

export function useWorkflow(code: string) {
  return useQuery({
    queryKey: queryKeys.workflows.detail(code),
    queryFn: () => workflowsApi.getByCode(code),
    enabled: !!code,
  })
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: WorkflowCreate) => workflowsApi.create(data),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all })
      toast({
        title: 'Workflow creado',
        description: `El workflow ${workflow.code} ha sido creado correctamente.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear el workflow.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateWorkflow() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ code, data }: { code: string; data: WorkflowUpdate }) =>
      workflowsApi.update(code, data),
    onSuccess: (workflow) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.detail(workflow.code) })
      toast({
        title: 'Workflow actualizado',
        description: `El workflow ${workflow.code} ha sido actualizado.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el workflow.',
        variant: 'destructive',
      })
    },
  })
}

export function useToggleWorkflowStatus() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ code, isActive }: { code: string; isActive: boolean }) =>
      workflowsApi.toggleStatus(code, isActive),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all })
      toast({
        title: result.is_active ? 'Workflow activado' : 'Workflow desactivado',
        description: `El workflow ${result.code} ha sido ${result.is_active ? 'activado' : 'desactivado'}.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo cambiar el estado del workflow.',
        variant: 'destructive',
      })
    },
  })
}

export function useDeleteWorkflow() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (code: string) => workflowsApi.delete(code),
    onSuccess: (_, code) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.all })
      toast({
        title: 'Workflow eliminado',
        description: `El workflow ${code} ha sido eliminado.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar el workflow.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// DOCUMENT REQUIREMENTS HOOKS
// =============================================================================

export function useDocumentRequirements(workflowCode: string) {
  return useQuery({
    queryKey: queryKeys.documents.byWorkflow(workflowCode),
    queryFn: () => documentsApi.getByWorkflow(workflowCode),
    enabled: !!workflowCode,
  })
}

export function useAddDocumentRequirement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ workflowCode, data }: { workflowCode: string; data: DocumentRequirementCreate }) =>
      documentsApi.add(workflowCode, data),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.byWorkflow(workflowCode) })
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.detail(workflowCode) })
      toast({
        title: 'Documento agregado',
        description: 'El documento requerido ha sido agregado al workflow.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo agregar el documento.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateDocumentRequirement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({
      workflowCode,
      documentCode,
      data,
    }: {
      workflowCode: string
      documentCode: string
      data: DocumentRequirementUpdate
    }) => documentsApi.update(workflowCode, documentCode, data),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.byWorkflow(workflowCode) })
      toast({
        title: 'Documento actualizado',
        description: 'El documento requerido ha sido actualizado.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el documento.',
        variant: 'destructive',
      })
    },
  })
}

export function useRemoveDocumentRequirement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ workflowCode, documentCode }: { workflowCode: string; documentCode: string }) =>
      documentsApi.remove(workflowCode, documentCode),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.byWorkflow(workflowCode) })
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.detail(workflowCode) })
      toast({
        title: 'Documento eliminado',
        description: 'El documento requerido ha sido eliminado del workflow.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar el documento.',
        variant: 'destructive',
      })
    },
  })
}

export function useReorderDocuments() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ workflowCode, order }: { workflowCode: string; order: DocumentReorderItem[] }) =>
      documentsApi.reorder(workflowCode, order),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents.byWorkflow(workflowCode) })
      toast({
        title: 'Orden actualizado',
        description: 'El orden de los documentos ha sido actualizado.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el orden.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// TARIFFS HOOKS
// =============================================================================

export function useTariffs(filters?: TariffFilters) {
  return useQuery({
    queryKey: queryKeys.tariffs.list(filters),
    queryFn: () => tariffsApi.getAll(filters),
  })
}

export function useCreateTariff() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: WorkflowTariffCreate) => tariffsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tariffs.all })
      toast({
        title: 'Tarifa creada',
        description: 'La tarifa ha sido creada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear la tarifa.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateTariff() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ tariffId, data }: { tariffId: number; data: WorkflowTariffUpdate }) =>
      tariffsApi.update(tariffId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tariffs.all })
      toast({
        title: 'Tarifa actualizada',
        description: 'La tarifa ha sido actualizada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar la tarifa.',
        variant: 'destructive',
      })
    },
  })
}

export function useDeleteTariff() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (tariffId: number) => tariffsApi.delete(tariffId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tariffs.all })
      toast({
        title: 'Tarifa eliminada',
        description: 'La tarifa ha sido eliminada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar la tarifa.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// TARIFF SUPPLEMENTS HOOKS
// =============================================================================

export function useSupplements(activeOnly?: boolean) {
  return useQuery({
    queryKey: queryKeys.supplements.list(activeOnly),
    queryFn: () => supplementsApi.getAll(activeOnly),
  })
}

export function useSupplement(code: string) {
  return useQuery({
    queryKey: queryKeys.supplements.detail(code),
    queryFn: () => supplementsApi.getByCode(code),
    enabled: !!code,
  })
}

export function useCreateSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: TariffSupplementCreate) => supplementsApi.create(data),
    onSuccess: (supplement) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.supplements.all })
      toast({
        title: 'Suplemento creado',
        description: `El suplemento ${supplement.code} ha sido creado correctamente.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ code, data }: { code: string; data: TariffSupplementUpdate }) =>
      supplementsApi.update(code, data),
    onSuccess: (supplement) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.supplements.all })
      queryClient.invalidateQueries({ queryKey: queryKeys.supplements.detail(supplement.code) })
      toast({
        title: 'Suplemento actualizado',
        description: `El suplemento ${supplement.code} ha sido actualizado.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

export function useDeleteSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (code: string) => supplementsApi.delete(code),
    onSuccess: (_, code) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.supplements.all })
      toast({
        title: 'Suplemento eliminado',
        description: `El suplemento ${code} ha sido eliminado.`,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// WORKFLOW SUPPLEMENTS HOOKS
// =============================================================================

export function useWorkflowSupplements(workflowCode: string) {
  return useQuery({
    queryKey: queryKeys.workflowSupplements.byWorkflow(workflowCode),
    queryFn: () => workflowSupplementsApi.getByWorkflow(workflowCode),
    enabled: !!workflowCode,
  })
}

export function useAddWorkflowSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ workflowCode, data }: { workflowCode: string; data: WorkflowSupplementConfigCreate }) =>
      workflowSupplementsApi.add(workflowCode, data),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowSupplements.byWorkflow(workflowCode) })
      queryClient.invalidateQueries({ queryKey: queryKeys.tariffs.all })
      toast({
        title: 'Suplemento agregado',
        description: 'El suplemento ha sido agregado al workflow.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo agregar el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateWorkflowSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({
      workflowCode,
      supplementCode,
      data,
    }: {
      workflowCode: string
      supplementCode: string
      data: WorkflowSupplementConfigUpdate
    }) => workflowSupplementsApi.update(workflowCode, supplementCode, data),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowSupplements.byWorkflow(workflowCode) })
      toast({
        title: 'Suplemento actualizado',
        description: 'La configuración del suplemento ha sido actualizada.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

export function useRemoveWorkflowSupplement() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ workflowCode, supplementCode }: { workflowCode: string; supplementCode: string }) =>
      workflowSupplementsApi.remove(workflowCode, supplementCode),
    onSuccess: (_, { workflowCode }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.workflowSupplements.byWorkflow(workflowCode) })
      queryClient.invalidateQueries({ queryKey: queryKeys.tariffs.all })
      toast({
        title: 'Suplemento eliminado',
        description: 'El suplemento ha sido eliminado del workflow.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar el suplemento.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// SLOT CONFIGS HOOKS
// =============================================================================

export function useSlotConfigs(filters?: SlotConfigFilters) {
  return useQuery({
    queryKey: queryKeys.appointments.slotConfigs.list(filters),
    queryFn: () => slotConfigsApi.getAll(filters),
  })
}

export function useCreateSlotConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: AppointmentSlotConfigCreate) => slotConfigsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.slotConfigs.all })
      toast({
        title: 'Horario creado',
        description: 'El horario de citas ha sido creado correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear el horario.',
        variant: 'destructive',
      })
    },
  })
}

export function useCreateSlotConfigBatch() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: AppointmentSlotConfigBatchCreate) => slotConfigsApi.createBatch(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.slotConfigs.all })
      const message = result.total_skipped > 0
        ? `${result.total_created} horario(s) creado(s), ${result.total_skipped} omitido(s) (ya existían).`
        : `${result.total_created} horario(s) creado(s) correctamente.`
      toast({
        title: 'Horarios creados',
        description: message,
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear los horarios.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateSlotConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ slotId, data }: { slotId: string; data: AppointmentSlotConfigUpdate }) =>
      slotConfigsApi.update(slotId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.slotConfigs.all })
      toast({
        title: 'Horario actualizado',
        description: 'El horario de citas ha sido actualizado correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar el horario.',
        variant: 'destructive',
      })
    },
  })
}

export function useBatchUpdateSlotConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: AppointmentSlotConfigGroupUpdate) => slotConfigsApi.batchUpdate(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.slotConfigs.all })
      const parts = []
      if (result.total_updated > 0) parts.push(`${result.total_updated} actualizado(s)`)
      if (result.total_created > 0) parts.push(`${result.total_created} creado(s)`)
      if (result.total_deleted > 0) parts.push(`${result.total_deleted} eliminado(s)`)
      toast({
        title: 'Horarios actualizados',
        description: parts.join(', ') + '.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar los horarios.',
        variant: 'destructive',
      })
    },
  })
}

export function useDeleteSlotConfig() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (slotId: string) => slotConfigsApi.delete(slotId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.slotConfigs.all })
      toast({
        title: 'Horario eliminado',
        description: 'El horario de citas ha sido eliminado correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar el horario.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// BLOCKED DATES HOOKS
// =============================================================================

export function useBlockedDates(filters?: BlockedDateFilters) {
  return useQuery({
    queryKey: queryKeys.appointments.blockedDates.list(filters),
    queryFn: () => blockedDatesApi.getAll(filters),
  })
}

export function useAddBlockedDate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: AppointmentBlockedDateCreate) => blockedDatesApi.add(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.blockedDates.all })
      toast({
        title: 'Fecha bloqueada',
        description: 'La fecha ha sido bloqueada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo bloquear la fecha.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateBlockedDate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ blockedDateId, data }: { blockedDateId: string; data: AppointmentBlockedDateUpdate }) =>
      blockedDatesApi.update(blockedDateId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.blockedDates.all })
      toast({
        title: 'Fecha actualizada',
        description: 'La fecha bloqueada ha sido actualizada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar la fecha.',
        variant: 'destructive',
      })
    },
  })
}

export function useRemoveBlockedDate() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (blockedDateId: string) => blockedDatesApi.remove(blockedDateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.blockedDates.all })
      toast({
        title: 'Fecha desbloqueada',
        description: 'La fecha ha sido desbloqueada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo desbloquear la fecha.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// DELAY RULES HOOKS
// =============================================================================

export function useDelayRules(workflowCode?: string) {
  return useQuery({
    queryKey: queryKeys.appointments.delayRules.list(workflowCode),
    queryFn: () => delayRulesApi.getAll(workflowCode),
  })
}

export function useCreateDelayRule() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (data: AppointmentDelayRuleCreate) => delayRulesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.delayRules.all })
      toast({
        title: 'Regla creada',
        description: 'La regla de espera ha sido creada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo crear la regla.',
        variant: 'destructive',
      })
    },
  })
}

export function useUpdateDelayRule() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: ({ ruleId, data }: { ruleId: string; data: AppointmentDelayRuleUpdate }) =>
      delayRulesApi.update(ruleId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.delayRules.all })
      toast({
        title: 'Regla actualizada',
        description: 'La regla de espera ha sido actualizada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo actualizar la regla.',
        variant: 'destructive',
      })
    },
  })
}

export function useDeleteDelayRule() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  return useMutation({
    mutationFn: (ruleId: string) => delayRulesApi.delete(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.appointments.delayRules.all })
      toast({
        title: 'Regla eliminada',
        description: 'La regla de espera ha sido eliminada correctamente.',
      })
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'No se pudo eliminar la regla.',
        variant: 'destructive',
      })
    },
  })
}

// =============================================================================
// EXTRACTION SCHEMAS HOOKS
// =============================================================================

export function useExtractionSchemas() {
  return useQuery({
    queryKey: queryKeys.extractionSchemas.all,
    queryFn: () => extractionSchemasApi.getAll(),
    staleTime: 60 * 60 * 1000, // 1h — schemas change very rarely
  })
}
