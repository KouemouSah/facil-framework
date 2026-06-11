/**
 * Entity Locations Types
 *
 * TypeScript interfaces for entity location management.
 * Cities and entities can be created dynamically.
 */

// Default entity codes (can be extended dynamically)
export const DEFAULT_ENTITY_CODES = [
  'CNEDOGE',
  'DGT',
  'EXTRANJERIA',
  'MINFP',
  'ONRC',
  'MINHV',
] as const

export type EntityCode = string

// Default cities (can be extended dynamically)
export const DEFAULT_CITIES = ['Malabo', 'Bata', 'Mongomo', 'Evinayong', 'Ebebiyin'] as const

export type City = string

// Valid regions (fixed - only Insular or Continental)
export const REGIONS = ['Insular', 'Continental'] as const

export type Region = (typeof REGIONS)[number]

// Default city to region mapping (used for auto-fill suggestions)
export const DEFAULT_CITY_REGION_MAP: Record<string, Region> = {
  Malabo: 'Insular',
  Bata: 'Continental',
  Mongomo: 'Continental',
  Evinayong: 'Continental',
  Ebebiyin: 'Continental',
}

// Operating hours for a single day
export interface DayHours {
  open: string
  close: string
}

// Operating hours for the week
export interface OperatingHours {
  monday?: DayHours | null
  tuesday?: DayHours | null
  wednesday?: DayHours | null
  thursday?: DayHours | null
  friday?: DayHours | null
  saturday?: DayHours | null
  sunday?: DayHours | null
}

// Entity location response from API
export interface EntityLocation {
  id: string
  entity_code: string
  city: string
  region: Region
  location_name: string
  location_address: string | null
  phone: string | null
  email: string | null
  is_main_office: boolean
  is_active: boolean
  operating_hours: OperatingHours | null
  notes: string | null
  created_at: string
  updated_at: string
}

// Create entity location request
export interface EntityLocationCreate {
  entity_code: string
  city: string
  region: Region
  location_name: string
  location_address?: string | null
  phone?: string | null
  email?: string | null
  is_main_office?: boolean
  is_active?: boolean
  operating_hours?: OperatingHours | null
  notes?: string | null
}

// Update entity location request
export interface EntityLocationUpdate {
  entity_code?: string
  city?: string
  region?: Region
  location_name?: string
  location_address?: string | null
  phone?: string | null
  email?: string | null
  is_main_office?: boolean
  is_active?: boolean
  operating_hours?: OperatingHours | null
  notes?: string | null
}

// Paginated list response
export interface EntityLocationListResponse {
  items: EntityLocation[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Query parameters for listing
export interface EntityLocationQueryParams {
  entity_code?: string
  city?: string
  region?: Region
  is_active?: boolean
  page?: number
  page_size?: number
}

// Simplified location for dropdowns
export interface EntityLocationSimple {
  id: string
  entity_code: string
  city: string
  region: Region
  location_name: string
  is_main_office: boolean
}

// Default entity info with display name (can be extended dynamically)
export const DEFAULT_ENTITY_INFO: Record<string, { name: string; description: string }> = {
  CNEDOGE: {
    name: 'CNEDOGE',
    description: 'Centro Nacional de Expedición de Documentos Oficiales',
  },
  DGT: {
    name: 'DGT',
    description: 'Dirección General de Tráfico',
  },
  EXTRANJERIA: {
    name: 'Extranjería',
    description: 'Oficina de Extranjería',
  },
  MINFP: {
    name: 'MINFP',
    description: 'Ministerio de la Función Pública',
  },
  ONRC: {
    name: 'ONRC',
    description: 'Oficina Nacional del Registro Civil',
  },
  MINHV: {
    name: 'MINHV',
    description: 'Ministerio de Hacienda y Vivienda',
  },
}

// Default city info with display details (can be extended dynamically)
export const DEFAULT_CITY_INFO: Record<string, { region: Region; description: string; isCapital: boolean }> = {
  Malabo: {
    region: 'Insular',
    description: 'Capital en la Isla de Bioko',
    isCapital: true,
  },
  Bata: {
    region: 'Continental',
    description: 'Ciudad más grande del continente',
    isCapital: false,
  },
  Mongomo: {
    region: 'Continental',
    description: 'Provincia de Wele-Nzas',
    isCapital: false,
  },
  Evinayong: {
    region: 'Continental',
    description: 'Provincia de Centro Sur',
    isCapital: false,
  },
  Ebebiyin: {
    region: 'Continental',
    description: 'Provincia de Kie-Ntem',
    isCapital: false,
  },
}

// Helper function to get region for a city (returns Continental for unknown cities)
export function getCityRegion(city: string): Region {
  return DEFAULT_CITY_REGION_MAP[city] ?? 'Continental'
}
