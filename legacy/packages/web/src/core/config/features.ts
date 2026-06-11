/**
 * Feature Flags Configuration
 *
 * Two-layer system:
 * 1. ENV vars (build-time defaults, always available)
 * 2. Backend API /api/v1/feature-flags (runtime overrides from system_rules DB)
 *
 * The frontend starts with env var defaults and fetches DB overrides
 * on first load. Admin can toggle flags in system_rules without redeploy.
 *
 * @module core/config
 */

// =============================================================================
// BUILD-TIME DEFAULTS (from environment variables)
// =============================================================================

export const FEATURE_DYNAMIC_MENUS =
  process.env.NEXT_PUBLIC_FEATURE_DYNAMIC_MENUS !== 'false';

export const FEATURE_DYNAMIC_WIDGETS =
  process.env.NEXT_PUBLIC_FEATURE_DYNAMIC_WIDGETS === 'true';

export const FEATURE_DYNAMIC_FORM_RENDERER =
  process.env.NEXT_PUBLIC_FEATURE_DYNAMIC_FORM !== 'false';

export const FEATURE_CACHE_FIRST_WIZARD =
  process.env.NEXT_PUBLIC_FEATURE_CACHE_FIRST_WIZARD !== 'false';

export const FEATURE_REDIS_CACHE =
  process.env.NEXT_PUBLIC_FEATURE_REDIS_CACHE === 'true';

export const FEATURE_DECLARATIONS =
  process.env.NEXT_PUBLIC_FEATURE_DECLARATIONS === 'true';

// =============================================================================
// FEATURES OBJECT (convenience)
// =============================================================================

export const FEATURES = {
  DYNAMIC_MENUS: FEATURE_DYNAMIC_MENUS,
  DYNAMIC_WIDGETS: FEATURE_DYNAMIC_WIDGETS,
  DYNAMIC_FORM_RENDERER: FEATURE_DYNAMIC_FORM_RENDERER,
  REDIS_CACHE: FEATURE_REDIS_CACHE,
  CACHE_FIRST_WIZARD: FEATURE_CACHE_FIRST_WIZARD,
  DECLARATIONS: FEATURE_DECLARATIONS,
} as const;

// =============================================================================
// RUNTIME OVERRIDES (from backend API)
// =============================================================================

let _runtimeFlags: Record<string, boolean> | null = null;

/**
 * Fetch feature flags from backend (cached for session).
 * Falls back to env var defaults if API unavailable.
 */
export async function loadRuntimeFlags(): Promise<Record<string, boolean>> {
  if (_runtimeFlags) return _runtimeFlags;

  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
    const res = await fetch(`${apiUrl}/api/v1/feature-flags`, {
      cache: 'default',
    });
    if (res.ok) {
      const data = await res.json();
      const flags: Record<string, boolean> = data.flags || {};
      _runtimeFlags = flags;
      return flags;
    }
  } catch {
    // API unavailable — use env var defaults
  }

  const empty: Record<string, boolean> = {};
  _runtimeFlags = empty;
  return empty;
}

/**
 * Check if a feature is enabled (runtime override > env var default).
 */
export function isFeatureEnabled(feature: keyof typeof FEATURES): boolean {
  // Runtime override takes precedence
  const runtimeKey = feature.toLowerCase();
  if (_runtimeFlags && runtimeKey in _runtimeFlags) {
    return _runtimeFlags[runtimeKey];
  }
  // Fallback to build-time default
  return FEATURES[feature] === true;
}

/**
 * Get all enabled features.
 */
export function getEnabledFeatures(): (keyof typeof FEATURES)[] {
  return (Object.keys(FEATURES) as (keyof typeof FEATURES)[]).filter(
    (key) => isFeatureEnabled(key)
  );
}

export default FEATURES;
