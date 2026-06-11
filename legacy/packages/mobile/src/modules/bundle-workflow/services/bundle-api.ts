/**
 * Bundle Workflow API — aligned with web (10 endpoints).
 *
 * Backend: app/modules/fiscal_services/api/bundle_workflow_routes.py
 * All paths centralized in @core/api/endpoints.ts (API_ENDPOINTS.bundleWorkflow).
 * All require authentication.
 */

import { apiGet, apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  MyCompaniesResponse,
  SearchCompanyResponse,
  BundleInitiateResponse,
  ClassifyPreviewResponse,
  BundlePaymentResult,
} from '../types';

/** GET /bundle-workflow/my-companies */
export async function getMyCompanies(fiscalYear?: number): Promise<MyCompaniesResponse> {
  return apiGet<MyCompaniesResponse>(
    API_ENDPOINTS.bundleWorkflow.myCompanies,
    fiscalYear ? { fiscal_year: fiscalYear } : undefined,
  );
}

/** GET /bundle-workflow/search-company?q=&limit= */
export async function searchCompany(q: string, limit = 10): Promise<SearchCompanyResponse> {
  return apiGet<SearchCompanyResponse>(API_ENDPOINTS.bundleWorkflow.searchCompany, { q, limit });
}

/** POST /bundle-workflow/initiate */
export async function initiate(companyId: string, fiscalYear?: number): Promise<BundleInitiateResponse> {
  return apiPost<BundleInitiateResponse>(API_ENDPOINTS.bundleWorkflow.initiate, {
    company_id: companyId,
    ...(fiscalYear ? { fiscal_year: fiscalYear } : {}),
  });
}

/** POST /bundle-workflow/classify-preview */
export async function classifyPreview(
  extraction: Record<string, unknown>,
  zoneId?: string,
): Promise<ClassifyPreviewResponse> {
  return apiPost<ClassifyPreviewResponse>(API_ENDPOINTS.bundleWorkflow.classifyPreview, {
    extraction,
    ...(zoneId ? { zone_id: zoneId } : {}),
  });
}

/** POST /bundle-workflow/initiate-from-upload */
export async function initiateFromUpload(
  extraction: Record<string, unknown>,
  fiscalYear?: number,
  zoneId?: string,
  commerceType?: string,
): Promise<BundleInitiateResponse> {
  return apiPost<BundleInitiateResponse>(API_ENDPOINTS.bundleWorkflow.initiateFromUpload, {
    extraction,
    ...(fiscalYear ? { fiscal_year: fiscalYear } : {}),
    ...(zoneId ? { zone_id: zoneId } : {}),
    ...(commerceType ? { commerce_type: commerceType } : {}),
  });
}

/** POST /bundle-workflow/validate-selection */
export async function validateSelection(
  licenseId: string,
  processingMode: string,
  selectedObligationIds?: string[],
): Promise<{ valid: boolean; selected_total: number; errors?: unknown[] }> {
  return apiPost(API_ENDPOINTS.bundleWorkflow.validateSelection, {
    license_id: licenseId,
    processing_mode: processingMode,
    ...(selectedObligationIds ? { selected_obligation_ids: selectedObligationIds } : {}),
  });
}

/** POST /bundle-workflow/initiate-payment */
export async function initiatePayment(params: {
  license_id: string;
  processing_mode: string;
  payment_method: string;
  selected_obligation_ids: string[];
  phone_number?: string;
  wizard_session_id?: string;
}): Promise<BundlePaymentResult> {
  return apiPost<BundlePaymentResult>(API_ENDPOINTS.bundleWorkflow.initiatePayment, params);
}

/** GET /bundle-workflow/my-companies/{company_id} */
export async function getMyCompanyDetail(companyId: string, fiscalYear?: number): Promise<unknown> {
  return apiGet(
    API_ENDPOINTS.bundleWorkflow.myCompanyDetail(companyId),
    fiscalYear ? { fiscal_year: fiscalYear } : undefined,
  );
}

/** GET /bundle-workflow/my-companies/{company_id}/payments */
export async function getMyCompanyPayments(
  companyId: string,
  page = 1,
  pageSize = 20,
): Promise<unknown> {
  return apiGet(API_ENDPOINTS.bundleWorkflow.myCompanyPayments(companyId), {
    page,
    page_size: pageSize,
  });
}

/**
 * GET /bundle-workflow/my-companies/{company_id}/license-pdf
 * Returns the path; caller is responsible for downloading via apiClient blob streaming.
 */
export function getMyCompanyLicensePdfPath(companyId: string, language = 'es'): string {
  return `${API_ENDPOINTS.bundleWorkflow.myCompanyLicensePdf(companyId)}?language=${encodeURIComponent(language)}`;
}
