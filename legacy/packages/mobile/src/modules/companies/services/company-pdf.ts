/**
 * Bundle license PDF download — fetch the streamed PDF from
 * `GET /bundle-workflow/my-companies/{id}/license-pdf` and open it via
 * the native share/preview UI.
 *
 * Different pattern from the vault download flow:
 *   - vault returns a Firebase signed URL (cached + opened directly).
 *   - bundle license is streamed from the backend, requiring our JWT.
 * We persist to the cache directory and hand off to `expo-sharing`.
 */

import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';

import { appConfig } from '@core/config/app';
import { getAccessToken } from '@core/auth/auth-storage';

export async function downloadLicensePdf(
  companyId: string,
  language: 'es' | 'fr' | 'en' = 'es',
): Promise<void> {
  const token = await getAccessToken();
  if (!token) {
    throw new Error('Not authenticated');
  }
  const url = `${appConfig.api.baseUrl}/api/v1/bundle-workflow/my-companies/${encodeURIComponent(
    companyId,
  )}/license-pdf?language=${encodeURIComponent(language)}`;
  const target = `${FileSystem.cacheDirectory ?? ''}license-${companyId}-${language}.pdf`;

  const result = await FileSystem.downloadAsync(url, target, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (result.status !== 200) {
    throw new Error(`Download failed (HTTP ${result.status})`);
  }

  const canShare = await Sharing.isAvailableAsync();
  if (!canShare) {
    throw new Error('Sharing not available on this device');
  }
  await Sharing.shareAsync(result.uri, {
    mimeType: 'application/pdf',
    UTI: 'com.adobe.pdf',
    dialogTitle: 'License PDF',
  });
}
