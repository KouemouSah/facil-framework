/**
 * Cities Hooks
 *
 * React Query hooks for cities and entities management.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type {
  CityCreate,
  CityUpdate,
  EntityCreate,
  EntityUpdate,
  EntityFilters,
  Region,
} from '../types'
import * as api from '../services/api'

// Query keys
export const citiesKeys = {
  all: ['cities'] as const,
  lists: () => [...citiesKeys.all, 'list'] as const,
  list: (filters: { region?: Region; is_active?: boolean }) =>
    [...citiesKeys.lists(), filters] as const,
  simple: (isActive: boolean) => [...citiesKeys.all, 'simple', isActive] as const,
  details: () => [...citiesKeys.all, 'detail'] as const,
  detail: (id: string) => [...citiesKeys.details(), id] as const,
}

export const entitiesKeys = {
  all: ['entities'] as const,
  lists: () => [...entitiesKeys.all, 'list'] as const,
  list: (filters: EntityFilters) => [...entitiesKeys.lists(), filters] as const,
  withDetails: (filters: EntityFilters) => [...entitiesKeys.all, 'with-details', filters] as const,
  simple: (isActive: boolean) => [...entitiesKeys.all, 'simple', isActive] as const,
  details: () => [...entitiesKeys.all, 'detail'] as const,
  detail: (id: string) => [...entitiesKeys.details(), id] as const,
  detailWithDetails: (id: string) => [...entitiesKeys.all, 'detail-with-details', id] as const,
  departments: (id: string) => [...entitiesKeys.all, 'departments', id] as const,
}

// ============================================================================
// City Hooks
// ============================================================================

export function useCities(params?: { region?: Region; is_active?: boolean }) {
  return useQuery({
    queryKey: citiesKeys.list(params || {}),
    queryFn: () => api.getCities(params),
  })
}

export function useCitiesSimple(isActive: boolean = true) {
  return useQuery({
    queryKey: citiesKeys.simple(isActive),
    queryFn: () => api.getCitiesSimple(isActive),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export function useCity(cityId: string) {
  return useQuery({
    queryKey: citiesKeys.detail(cityId),
    queryFn: () => api.getCityById(cityId),
    enabled: !!cityId,
  })
}

export function useCreateCity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: CityCreate) => api.createCity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: citiesKeys.all })
    },
  })
}

export function useUpdateCity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ cityId, data }: { cityId: string; data: CityUpdate }) =>
      api.updateCity(cityId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: citiesKeys.all })
      queryClient.invalidateQueries({ queryKey: citiesKeys.detail(variables.cityId) })
    },
  })
}

export function useDeleteCity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (cityId: string) => api.deleteCity(cityId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: citiesKeys.all })
    },
  })
}

// ============================================================================
// Entity Hooks
// ============================================================================

export function useEntities(params?: EntityFilters) {
  return useQuery({
    queryKey: entitiesKeys.list(params || {}),
    queryFn: () => api.getEntities(params),
  })
}

export function useEntitiesWithDetails(params?: EntityFilters) {
  return useQuery({
    queryKey: entitiesKeys.withDetails(params || {}),
    queryFn: () => api.getEntitiesWithDetails(params),
  })
}

export function useEntitiesSimple(isActive: boolean = true) {
  return useQuery({
    queryKey: entitiesKeys.simple(isActive),
    queryFn: () => api.getEntitiesSimple(isActive),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

export function useEntity(entityId: string) {
  return useQuery({
    queryKey: entitiesKeys.detail(entityId),
    queryFn: () => api.getEntityById(entityId),
    enabled: !!entityId,
  })
}

export function useEntityWithDetails(entityId: string) {
  return useQuery({
    queryKey: entitiesKeys.detailWithDetails(entityId),
    queryFn: () => api.getEntityWithDetails(entityId),
    enabled: !!entityId,
  })
}

export function useEntityDepartments(entityId: string) {
  return useQuery({
    queryKey: entitiesKeys.departments(entityId),
    queryFn: () => api.getEntityDepartments(entityId),
    enabled: !!entityId,
  })
}

export function useCreateEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: EntityCreate) => api.createEntity(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entitiesKeys.all })
    },
  })
}

export function useUpdateEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ entityId, data }: { entityId: string; data: EntityUpdate }) =>
      api.updateEntity(entityId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: entitiesKeys.all })
      queryClient.invalidateQueries({ queryKey: entitiesKeys.detail(variables.entityId) })
    },
  })
}

export function useDeleteEntity() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (entityId: string) => api.deleteEntity(entityId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entitiesKeys.all })
    },
  })
}
