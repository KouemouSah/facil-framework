/**
 * Spacing and border-radius tokens
 *
 * Consistent spatial rhythm across the app. Uses a 4px base grid.
 */

export const spacing = {
  /** 4px — tight inline gaps */
  xs: 4,
  /** 8px — default inline gap, icon padding */
  sm: 8,
  /** 16px — standard component padding */
  md: 16,
  /** 24px — section spacing */
  lg: 24,
  /** 32px — card / group spacing */
  xl: 32,
  /** 48px — page-level spacing */
  xxl: 48,
} as const;

export const borderRadius = {
  /** 8px — subtle rounding (inputs, chips) */
  sm: 8,
  /** 12px — cards, dialogs */
  md: 12,
  /** 16px — larger cards, bottom sheets */
  lg: 16,
  /** 28px — FABs, pills */
  xl: 28,
  /** Full circle */
  full: 9999,
} as const;

export type SpacingKey = keyof typeof spacing;
export type BorderRadiusKey = keyof typeof borderRadius;
