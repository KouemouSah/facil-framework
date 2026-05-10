/**
 * Verification API - License verification by NIF or registration number
 */

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type { LicenseVerification } from '@modules/inspections/types/inspection.types';

export const verificationApi = {
  /** Verify by NIF (GExxxxx) or registration number (PE-xxxxxx) */
  verifyByIdentifier: (identifier: string) =>
    apiGet<LicenseVerification>(API_ENDPOINTS.inspections.verify, { nif: identifier }),

  /** Verify by license UUID (from QR code lid param) */
  verifyByLicenseId: (licenseId: string) =>
    apiGet<LicenseVerification>(API_ENDPOINTS.inspections.verify, { license_id: licenseId }),
};
