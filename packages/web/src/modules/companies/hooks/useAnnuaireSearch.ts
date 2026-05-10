'use client'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { companyPublicApi } from '../services/api'
import type { PublicDirectoryResponse, PublicZone } from '../types'

// =============================================================================
// QUERY KEYS
// =============================================================================

const ANNUAIRE_KEYS = {
  all: ['annuaire'] as const,
  search: (params: AnnuaireSearchParams) => [...ANNUAIRE_KEYS.all, 'search', params] as const,
  zones: () => [...ANNUAIRE_KEYS.all, 'zones'] as const,
  sectors: () => [...ANNUAIRE_KEYS.all, 'sectors'] as const,
  provincias: () => [...ANNUAIRE_KEYS.all, 'provincias'] as const,
  ciudades: (provincia?: string) => [...ANNUAIRE_KEYS.all, 'ciudades', provincia] as const,
  formas: () => [...ANNUAIRE_KEYS.all, 'formas'] as const,
}

// =============================================================================
// TYPES
// =============================================================================

export interface AnnuaireSearchParams {
  q?: string
  zone_id?: string
  sector?: string
  forma_juridica?: string
  provincia?: string
  ciudad?: string
  sort_by?: string
  sort_order?: string
  page?: number
  page_size?: number
}

type FormaCount = { value: string; count: number }

// =============================================================================
// HOOKS
// =============================================================================

/** Main directory search with 60s staleTime (backend caches 30s) */
export function useAnnuaireSearch(params: AnnuaireSearchParams, enabled = true) {
  return useQuery<PublicDirectoryResponse>({
    queryKey: ANNUAIRE_KEYS.search(params),
    queryFn: () => companyPublicApi.search(params),
    staleTime: 60_000,
    enabled,
  })
}

/** Filter options — long staleTime (rarely change) */
export function useAnnuaireZones() {
  return useQuery<PublicZone[]>({
    queryKey: ANNUAIRE_KEYS.zones(),
    queryFn: () => companyPublicApi.getZones(),
    staleTime: 5 * 60_000,
  })
}

export function useAnnuaireSectors() {
  return useQuery<string[]>({
    queryKey: ANNUAIRE_KEYS.sectors(),
    queryFn: () => companyPublicApi.getSectors(),
    staleTime: 5 * 60_000,
  })
}

export function useAnnuaireProvincias() {
  return useQuery<string[]>({
    queryKey: ANNUAIRE_KEYS.provincias(),
    queryFn: () => companyPublicApi.getProvincias(),
    staleTime: 5 * 60_000,
  })
}

export function useAnnuaireCiudades(provincia?: string) {
  return useQuery<string[]>({
    queryKey: ANNUAIRE_KEYS.ciudades(provincia),
    queryFn: () => companyPublicApi.getCiudades(provincia),
    staleTime: 5 * 60_000,
    enabled: !!provincia,
  })
}

export function useAnnuaireFormas() {
  return useQuery<FormaCount[]>({
    queryKey: ANNUAIRE_KEYS.formas(),
    queryFn: () => companyPublicApi.getFormasJuridicas(),
    staleTime: 5 * 60_000,
  })
}

// =============================================================================
// PREFETCH HELPER
// =============================================================================

/** Prefetch the next page on hover over pagination button */
export function useAnnuairePrefetch() {
  const queryClient = useQueryClient()

  return (params: AnnuaireSearchParams) => {
    queryClient.prefetchQuery({
      queryKey: ANNUAIRE_KEYS.search(params),
      queryFn: () => companyPublicApi.search(params),
      staleTime: 60_000,
    })
  }
}
