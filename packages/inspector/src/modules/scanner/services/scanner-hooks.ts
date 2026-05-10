/**
 * Scanner Hooks - QR Verification via API
 *
 * Wraps the verification API to look up a license by its UUID (lid)
 * extracted from a QR code scan.
 */

import { useMutation } from '@tanstack/react-query';
import { verificationApi } from '@modules/verification/services/verification-api';
import type { LicenseQRData } from './qr-parser';
import type { LicenseVerification } from '@modules/inspections/types/inspection.types';

/**
 * Hook that verifies a license from QR code data.
 * Uses mutation (not query) because scanning is an imperative action.
 *
 * Returns { mutateAsync, isPending, error, data } to call from scan handler.
 */
export function useQRVerification() {
  return useMutation<LicenseVerification, Error, LicenseQRData>({
    mutationFn: async (qrData: LicenseQRData) => {
      return verificationApi.verifyByLicenseId(qrData.lid);
    },
  });
}
