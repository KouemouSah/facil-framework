/**
 * Entity Locations React Query Hooks
 *
 * Custom hooks for entity locations data fetching and mutations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'

import type {
  EntityLocation,
  EntityLocationCreate,
  EntityLocationUpdate,
  EntityLocationListResponse,
  EntityLocationQueryParams,
  EntityCode,
  City,
} from '../types'

import {
  getEntityLocations,
  getEntityLocationById,
  getLocationsByEntity,
  getLocationsByCity,
  getLocationsByRegion,
  createEntityLocation,
  updateEntityLocation,
  deleteEntityLocation,
  toggleEntityLocationActive,
} from '../services/api'

// Query keys
export const entityLocationKeys = {
  all: ['entity-locations'] as const,
  lists: () => [...entityLocationKeys.all, 'list'] as const,
  list: (params?: EntityLocationQueryParams) => [...entityLocationKeys.lists(), params] as const,
  details: () => [...entityLocationKeys.all, 'detail'] as const,
  detail: (id: string) => [...entityLocationKeys.details(), id] as const,
  byEntity: (entityCode: EntityCode) => [...entityLocationKeys.all, 'by-entity', entityCode] as const,
  byCity: (city: City) => [...entityLocationKeys.all, 'by-city', city] as const,
  byRegion: (region: string) => [...entityLocationKeys.all, 'by-region', region] as const,
}

/**
 * Hook to fetch paginated entity locations
 */
export function useEntityLocations(params?: EntityLocationQueryParams) {
  return useQuery<EntityLocationListResponse>({
    queryKey: entityLocationKeys.list(params),
    queryFn: () => getEntityLocations(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch a single entity location by ID
 */
export function useEntityLocation(id: string) {
  return useQuery<EntityLocation>({
    queryKey: entityLocationKeys.detail(id),
    queryFn: () => getEntityLocationById(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to fetch locations by entity code (public)
 */
export function useLocationsByEntity(entityCode: EntityCode, enabled = true) {
  return useQuery<EntityLocation[]>({
    queryKey: entityLocationKeys.byEntity(entityCode),
    queryFn: () => getLocationsByEntity(entityCode),
    enabled: enabled && !!entityCode,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to fetch locations by city (public)
 */
export function useLocationsByCity(city: City, enabled = true) {
  return useQuery<EntityLocation[]>({
    queryKey: entityLocationKeys.byCity(city),
    queryFn: () => getLocationsByCity(city),
    enabled: enabled && !!city,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to fetch locations by region (public)
 */
export function useLocationsByRegion(region: 'Insular' | 'Continental', enabled = true) {
  return useQuery<EntityLocation[]>({
    queryKey: entityLocationKeys.byRegion(region),
    queryFn: () => getLocationsByRegion(region),
    enabled: enabled && !!region,
    staleTime: 5 * 60 * 1000,
  })
}

/**
 * Hook to create a new entity location
 */
export function useCreateEntityLocation() {
  const queryClient = useQueryClient()

  return useMutation<EntityLocation, Error, EntityLocationCreate>({
    mutationFn: createEntityLocation,
    onSuccess: (data) => {
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: entityLocationKeys.all })
      toast.success(`Location "${data.location_name}" created successfully`)
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to create location')
    },
  })
}

/**
 * Hook to update an entity location
 */
export function useUpdateEntityLocation() {
  const queryClient = useQueryClient()

  return useMutation<EntityLocation, Error, { id: string; data: EntityLocationUpdate }>({
    mutationFn: ({ id, data }) => updateEntityLocation(id, data),
    onSuccess: (data) => {
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: entityLocationKeys.all })
      toast.success(`Location "${data.location_name}" updated successfully`)
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to update location')
    },
  })
}

/**
 * Hook to delete an entity location
 */
export function useDeleteEntityLocation() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, string>({
    mutationFn: deleteEntityLocation,
    onSuccess: () => {
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: entityLocationKeys.all })
      toast.success('Location deleted successfully')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to delete location')
    },
  })
}

/**
 * Hook to toggle location active status
 */
export function useToggleEntityLocationActive() {
  const queryClient = useQueryClient()

  return useMutation<EntityLocation, Error, string>({
    mutationFn: toggleEntityLocationActive,
    onSuccess: (data) => {
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: entityLocationKeys.all })
      toast.success(
        `Location "${data.location_name}" ${data.is_active ? 'activated' : 'deactivated'}`
      )
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to toggle location status')
    },
  })
}
