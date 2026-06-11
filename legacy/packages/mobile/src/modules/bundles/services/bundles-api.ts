/**
 * Service Bundles catalog (commerce types, zones, simulator).
 * Backend: app/modules/fiscal_services/api/bundle_routes.py
 * All paths centralized via API_ENDPOINTS.serviceBundles.
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  CommerceType,
  CommerceZone,
  MyCompaniesResponse,
  MyCompanyDetail,
  MyCompanyPaymentsResponse,
  SimulatorResponse,
} from '../types/bundles.types';

export async function getCommerceTypes(): Promise<CommerceType[]> {
  return apiGet<CommerceType[]>(API_ENDPOINTS.serviceBundles.commerceTypes);
}

export async function getZones(): Promise<CommerceZone[]> {
  return apiGet<CommerceZone[]>(API_ENDPOINTS.serviceBundles.zones);
}

export async function simulate(commerceType: string, zoneCode: string): Promise<SimulatorResponse> {
  return apiGet<SimulatorResponse>(API_ENDPOINTS.serviceBundles.simulator, {
    commerce_type: commerceType,
    zone_code: zoneCode,
  });
}

// ---------------------------------------------------------------------------
// Citizen — Mes entreprises (BUNDLE_PAYMENT route group)
// Wired to bundle_workflow_routes.py (no agent permission, scoped to user via
// user_company_roles).
// ---------------------------------------------------------------------------

export async function getMyCompanies(fiscalYear?: number): Promise<MyCompaniesResponse> {
  return apiGet<MyCompaniesResponse>(
    API_ENDPOINTS.bundleWorkflow.myCompanies,
    fiscalYear ? { fiscal_year: fiscalYear } : undefined,
  );
}

export async function getMyCompanyDetail(
  companyId: string,
  fiscalYear?: number,
): Promise<MyCompanyDetail> {
  return apiGet<MyCompanyDetail>(
    API_ENDPOINTS.bundleWorkflow.myCompanyDetail(companyId),
    fiscalYear ? { fiscal_year: fiscalYear } : undefined,
  );
}

export async function getMyCompanyPayments(
  companyId: string,
  page = 1,
  pageSize = 20,
): Promise<MyCompanyPaymentsResponse> {
  return apiGet<MyCompanyPaymentsResponse>(
    API_ENDPOINTS.bundleWorkflow.myCompanyPayments(companyId),
    { page, page_size: pageSize },
  );
}
