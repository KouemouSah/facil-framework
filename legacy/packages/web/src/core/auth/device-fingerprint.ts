/**
 * Lightweight device fingerprint for 2FA device binding.
 *
 * Generates a stable hash based on browser characteristics.
 * NOT meant for tracking — only for detecting device changes during 2FA setup.
 * No external dependencies (uses Web Crypto API).
 */

async function sha256(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

function getComponents(): string[] {
  if (typeof window === 'undefined') return ['ssr'];

  const nav = navigator;
  const screen = window.screen;

  return [
    nav.userAgent,
    nav.language,
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    String(nav.hardwareConcurrency || 0),
    String(nav.maxTouchPoints || 0),
    nav.platform || '',
  ];
}

/**
 * Generate a device fingerprint hash.
 * Returns a 64-char hex string (SHA-256) that is stable for the same browser+device.
 */
export async function getDeviceFingerprint(): Promise<string> {
  const components = getComponents();
  return sha256(components.join('|'));
}

/**
 * Get device info object for session creation.
 */
export function getDeviceInfo(): Record<string, string> {
  if (typeof window === 'undefined') return {};

  const nav = navigator;
  return {
    platform: nav.platform || 'unknown',
    language: nav.language || 'unknown',
    screen: `${screen.width}x${screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
}
