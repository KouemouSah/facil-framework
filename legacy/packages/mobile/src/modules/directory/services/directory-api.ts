/**
 * Public Companies Directory (annuaire public).
 * Backend: app/modules/companies/api/company_public_routes.py
 * All paths centralized via API_ENDPOINTS.publicCompanies.
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type { DirectorySearchResponse, FilterOption } from '../types/directory.types';

export async function searchDirectory(
  params: Record<string, string>,
): Promise<DirectorySearchResponse> {
  return apiGet<DirectorySearchResponse>(API_ENDPOINTS.publicCompanies.search, params);
}

export async function getZones(): Promise<FilterOption[]> {
  return apiGet<FilterOption[]>(API_ENDPOINTS.publicCompanies.zones);
}

export async function getSectors(): Promise<FilterOption[]> {
  return apiGet<FilterOption[]>(API_ENDPOINTS.publicCompanies.sectors);
}

export async function getProvincias(): Promise<FilterOption[]> {
  return apiGet<FilterOption[]>(API_ENDPOINTS.publicCompanies.provincias);
}

export async function getCiudades(provincia?: string): Promise<FilterOption[]> {
  return apiGet<FilterOption[]>(
    API_ENDPOINTS.publicCompanies.ciudades,
    provincia ? { provincia } : undefined,
  );
}

export async function getFormasJuridicas(): Promise<FilterOption[]> {
  return apiGet<FilterOption[]>(API_ENDPOINTS.publicCompanies.formasJuridicas);
}
