/**
 * Entity Locations API Service
 *
 * API client for entity locations CRUD operations.
 */

import apiClient from '@/core/api/client'
import type {
  EntityLocation,
  EntityLocationCreate,
  EntityLocationUpdate,
  EntityLocationListResponse,
  EntityLocationQueryParams,
  EntityCode,
  City,
} from '../types'

const BASE_URL = '/entity-locations'

/**
 * Get paginated list of entity locations with optional filters
 */
export async function getEntityLocations(
  params?: EntityLocationQueryParams
): Promise<EntityLocationListResponse> {
  const response = await apiClient.get<EntityLocationListResponse>(BASE_URL, { params })
  return response.data
}

/**
 * Get a single entity location by ID
 */
export async function getEntityLocationById(id: string): Promise<EntityLocation> {
  const response = await apiClient.get<EntityLocation>(`${BASE_URL}/${id}`)
  return response.data
}

/**
 * Get all locations for a specific entity (public endpoint)
 */
export async function getLocationsByEntity(entityCode: EntityCode): Promise<EntityLocation[]> {
  const response = await apiClient.get<EntityLocation[]>(`${BASE_URL}/by-entity/${entityCode}`)
  return response.data
}

/**
 * Get all locations in a specific city (public endpoint)
 */
export async function getLocationsByCity(city: City): Promise<EntityLocation[]> {
  const response = await apiClient.get<EntityLocation[]>(`${BASE_URL}/by-city/${city}`)
  return response.data
}

/**
 * Get all locations in a specific region (public endpoint)
 */
export async function getLocationsByRegion(region: 'Insular' | 'Continental'): Promise<EntityLocation[]> {
  const response = await apiClient.get<EntityLocation[]>(`${BASE_URL}/by-region/${region}`)
  return response.data
}

/**
 * Create a new entity location (admin only)
 */
export async function createEntityLocation(data: EntityLocationCreate): Promise<EntityLocation> {
  const response = await apiClient.post<EntityLocation>(BASE_URL, data)
  return response.data
}

/**
 * Update an existing entity location (admin only)
 */
export async function updateEntityLocation(
  id: string,
  data: EntityLocationUpdate
): Promise<EntityLocation> {
  const response = await apiClient.put<EntityLocation>(`${BASE_URL}/${id}`, data)
  return response.data
}

/**
 * Delete an entity location (admin only)
 */
export async function deleteEntityLocation(id: string): Promise<void> {
  await apiClient.delete(`${BASE_URL}/${id}`)
}

/**
 * Toggle the active status of a location (admin only)
 */
export async function toggleEntityLocationActive(id: string): Promise<EntityLocation> {
  const response = await apiClient.patch<EntityLocation>(`${BASE_URL}/${id}/toggle-active`)
  return response.data
}

/**
 * Get list of valid entity codes
 */
export async function getValidEntityCodes(): Promise<string[]> {
  const response = await apiClient.get<string[]>(`${BASE_URL}/meta/entities`)
  return response.data
}

/**
 * Get list of valid cities
 */
export async function getValidCities(): Promise<string[]> {
  const response = await apiClient.get<string[]>(`${BASE_URL}/meta/cities`)
  return response.data
}
