/**
 * Cities API Service
 *
 * API calls for cities and entities management.
 */

import apiClient from '@/core/api/client'
import type {
  City,
  CitySimple,
  CityCreate,
  CityUpdate,
  CityListResponse,
  Entity,
  EntitySimple,
  EntityWithDetails,
  EntityCreate,
  EntityUpdate,
  EntityListResponse,
  EntityWithDetailsListResponse,
  EntityFilters,
  Region,
} from '../types'

// ============================================================================
// City API
// ============================================================================

export async function getCities(params?: {
  region?: Region
  is_active?: boolean
}): Promise<CityListResponse> {
  const response = await apiClient.get<CityListResponse>('/cities', { params })
  return response.data
}

export async function getCitiesSimple(isActive: boolean = true): Promise<CitySimple[]> {
  const response = await apiClient.get<CitySimple[]>('/cities/simple', {
    params: { is_active: isActive },
  })
  return response.data
}

export async function getCityById(cityId: string): Promise<City> {
  const response = await apiClient.get<City>(`/cities/${cityId}`)
  return response.data
}

export async function createCity(data: CityCreate): Promise<City> {
  const response = await apiClient.post<City>('/cities', data)
  return response.data
}

export async function updateCity(cityId: string, data: CityUpdate): Promise<City> {
  const response = await apiClient.patch<City>(`/cities/${cityId}`, data)
  return response.data
}

export async function deleteCity(cityId: string): Promise<void> {
  await apiClient.delete(`/cities/${cityId}`)
}

// ============================================================================
// Entity API
// ============================================================================

export async function getEntities(params?: EntityFilters): Promise<EntityListResponse> {
  const response = await apiClient.get<EntityListResponse>('/entities', { params })
  return response.data
}

export async function getEntitiesWithDetails(
  params?: EntityFilters
): Promise<EntityWithDetailsListResponse> {
  const response = await apiClient.get<EntityWithDetailsListResponse>('/entities/with-details', {
    params,
  })
  return response.data
}

export async function getEntitiesSimple(isActive: boolean = true): Promise<EntitySimple[]> {
  const response = await apiClient.get<EntitySimple[]>('/entities/simple', {
    params: { is_active: isActive },
  })
  return response.data
}

export async function getEntityById(entityId: string): Promise<Entity> {
  const response = await apiClient.get<Entity>(`/entities/${entityId}`)
  return response.data
}

export async function getEntityWithDetails(entityId: string): Promise<EntityWithDetails> {
  const response = await apiClient.get<EntityWithDetails>(`/entities/${entityId}/details`)
  return response.data
}

export async function getEntityDepartments(entityId: string): Promise<Entity[]> {
  const response = await apiClient.get<Entity[]>(`/entities/${entityId}/departments`)
  return response.data
}

export async function createEntity(data: EntityCreate): Promise<Entity> {
  const response = await apiClient.post<Entity>('/entities', data)
  return response.data
}

export async function updateEntity(entityId: string, data: EntityUpdate): Promise<Entity> {
  const response = await apiClient.patch<Entity>(`/entities/${entityId}`, data)
  return response.data
}

export async function deleteEntity(entityId: string): Promise<void> {
  await apiClient.delete(`/entities/${entityId}`)
}
