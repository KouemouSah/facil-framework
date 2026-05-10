/**
 * QR Code Parser - License QR Data Extraction
 *
 * Parses QR codes from commercial license documents.
 * Expected URL format:
 *   https://taxasge.emacsah.com/verify/LIC-2026-8BCA71AB?t=ac14070ce2601d0d&lid=8bca71ab-b0d7-4b97-a70d-de5845a53f01
 *
 * Extracts: licenseRef (LIC-XXXX-XXXXXXXX), lid (UUID), token (t param)
 */

export interface LicenseQRData {
  /** License reference code, e.g. "LIC-2026-8BCA71AB" */
  licenseRef: string;
  /** License UUID from the lid query param */
  lid: string;
  /** Verification token from the t query param */
  token: string;
}

/**
 * Pattern: URL path must contain /verify/LIC- followed by reference chars,
 * and query string must include t= and lid= params.
 */
const LICENSE_PATH_PATTERN = /\/verify\/(LIC-[A-Za-z0-9-]+)/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Parse a scanned QR code string into structured license data.
 *
 * @param data - Raw string from QR code scan
 * @returns Parsed license data, or null if format doesn't match
 */
export function parseLicenseQR(data: string): LicenseQRData | null {
  if (!data || typeof data !== 'string') return null;

  const trimmed = data.trim();

  // Must be a URL containing /verify/LIC-
  const pathMatch = trimmed.match(LICENSE_PATH_PATTERN);
  if (!pathMatch) return null;

  const licenseRef = pathMatch[1];

  // Parse query parameters
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return null;
  }

  const token = url.searchParams.get('t');
  const lid = url.searchParams.get('lid');

  if (!token || !lid) return null;

  // Validate lid is a valid UUID format
  if (!UUID_PATTERN.test(lid)) return null;

  // Validate token is non-empty hex string
  if (!/^[0-9a-f]+$/i.test(token)) return null;

  return {
    licenseRef,
    lid,
    token,
  };
}
