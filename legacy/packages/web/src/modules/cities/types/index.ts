/**
 * Cities Types
 *
 * TypeScript interfaces for cities and entities management.
 */

// Valid regions (fixed)
export const REGIONS = ['Insular', 'Continental'] as const
export type Region = (typeof REGIONS)[number]

// City interfaces
export interface City {
  id: string
  name: string
  region: Region
  description: string | null
  is_capital: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CitySimple {
  id: string
  name: string
  region: Region
  is_capital: boolean
}

export interface CityCreate {
  name: string
  region: Region
  description?: string | null
  is_capital?: boolean
  is_active?: boolean
}

export interface CityUpdate {
  name?: string
  region?: Region
  description?: string | null
  is_capital?: boolean
  is_active?: boolean
}

export interface CityListResponse {
  items: City[]
  total: number
}

// Entity type enum
export const ENTITY_TYPES = ['entity', 'department', 'treasury'] as const
export type EntityType = (typeof ENTITY_TYPES)[number]

// Entity interfaces
export interface Entity {
  id: string
  code: string
  name: string
  description: string | null
  entity_type: EntityType
  parent_entity_id: string | null
  ministry_id: number | null
  workflow_codes: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface EntitySimple {
  id: string
  code: string
  name: string
  entity_type: EntityType
}

export interface EntityWithDetails extends Entity {
  parent_entity_code: string | null
  parent_entity_name: string | null
  ministry_code: string | null
  ministry_name: string | null
  resolved_workflow_codes: string[]
  workflow_count: number
}

export interface EntityCreate {
  code: string
  name: string
  description?: string | null
  entity_type?: EntityType
  parent_entity_id?: string | null
  ministry_id?: number | null
  workflow_codes?: string[]
  is_active?: boolean
}

export interface EntityUpdate {
  code?: string
  name?: string
  description?: string | null
  entity_type?: EntityType
  parent_entity_id?: string | null
  ministry_id?: number | null
  workflow_codes?: string[]
  is_active?: boolean
}

export interface EntityListResponse {
  items: Entity[]
  total: number
}

export interface EntityWithDetailsListResponse {
  items: EntityWithDetails[]
  total: number
}

// Entity filters for API calls
export interface EntityFilters {
  entity_type?: EntityType
  ministry_id?: number
  is_active?: boolean
}
