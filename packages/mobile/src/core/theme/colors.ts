/**
 * Material Design 3 color palette for Facil
 *
 * Inspired by the flag of Equatorial Guinea:
 * - Primary: Forest green (dominant national color)
 * - Tertiary: Teal accent (government trust)
 * - Error/Rejected: Red (flag accent)
 * - Semantic status colors for workflow states
 */

export const colors = {
  light: {
    // ── Primary (Forest Green) ──────────────────────────────────────────
    primary: '#0D6E3F',
    onPrimary: '#FFFFFF',
    primaryContainer: '#B8F0D0',
    onPrimaryContainer: '#00210E',

    // ── Secondary (Muted Green-Gray) ────────────────────────────────────
    secondary: '#4E6355',
    onSecondary: '#FFFFFF',
    secondaryContainer: '#D0E8D6',
    onSecondaryContainer: '#0B1F14',

    // ── Tertiary (Teal Accent) ──────────────────────────────────────────
    tertiary: '#3B6470',
    onTertiary: '#FFFFFF',
    tertiaryContainer: '#BEE9F7',
    onTertiaryContainer: '#001F28',

    // ── Error ───────────────────────────────────────────────────────────
    error: '#BA1A1A',
    onError: '#FFFFFF',
    errorContainer: '#FFDAD6',

    // ── Surfaces ────────────────────────────────────────────────────────
    background: '#F8FBF8',
    onBackground: '#191C19',
    surface: '#F8FBF8',
    onSurface: '#191C19',
    surfaceVariant: '#DDE5DB',
    onSurfaceVariant: '#414941',
    outline: '#717971',
    outlineVariant: '#C1C9BF',

    // ── Elevation levels (tinted surface) ───────────────────────────────
    elevation: {
      level0: 'transparent',
      level1: '#EFF5EF',
      level2: '#E8F0E8',
      level3: '#E1EBE1',
      level4: '#DFEAD0',
      level5: '#DAEADA',
    },

    // ── Semantic (workflow status) ──────────────────────────────────────
    success: '#0D6E3F',
    warning: '#F59E0B',
    info: '#3B6470',
    pending: '#F59E0B',
    approved: '#0D6E3F',
    rejected: '#BA1A1A',
    processing: '#3B6470',
  },

  dark: {
    // ── Primary ─────────────────────────────────────────────────────────
    primary: '#9CD8B4',
    onPrimary: '#00391C',
    primaryContainer: '#00522C',
    onPrimaryContainer: '#B8F0D0',

    // ── Secondary ───────────────────────────────────────────────────────
    secondary: '#B4CCBB',
    onSecondary: '#203528',
    secondaryContainer: '#364B3E',
    onSecondaryContainer: '#D0E8D6',

    // ── Tertiary ────────────────────────────────────────────────────────
    tertiary: '#A3CDDB',
    onTertiary: '#023640',
    tertiaryContainer: '#214C58',
    onTertiaryContainer: '#BEE9F7',

    // ── Error ───────────────────────────────────────────────────────────
    error: '#FFB4AB',
    onError: '#690005',
    errorContainer: '#93000A',

    // ── Surfaces ────────────────────────────────────────────────────────
    background: '#191C19',
    onBackground: '#E1E3DE',
    surface: '#191C19',
    onSurface: '#E1E3DE',
    surfaceVariant: '#414941',
    onSurfaceVariant: '#C1C9BF',
    outline: '#8B938A',
    outlineVariant: '#414941',

    // ── Elevation levels (tinted surface) ───────────────────────────────
    elevation: {
      level0: 'transparent',
      level1: '#1E2B1E',
      level2: '#233223',
      level3: '#283828',
      level4: '#2A3A2A',
      level5: '#2D3F2D',
    },

    // ── Semantic (workflow status) ──────────────────────────────────────
    success: '#9CD8B4',
    warning: '#FFD166',
    info: '#A3CDDB',
    pending: '#FFD166',
    approved: '#9CD8B4',
    rejected: '#FFB4AB',
    processing: '#A3CDDB',
  },
} as const;

/** Union of all semantic status color keys. */
export type SemanticColor =
  | 'success'
  | 'warning'
  | 'info'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'processing';

/** Light or dark color scheme keys. */
export type ColorScheme = keyof typeof colors;
