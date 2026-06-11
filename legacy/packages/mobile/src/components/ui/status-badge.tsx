/**
 * Colored badge for workflow / payment status
 *
 * Maps a status string to a semantic color from the theme and renders it
 * as a compact react-native-paper Chip.
 */

import { StyleSheet } from 'react-native';
import { Chip } from 'react-native-paper';

import { useAppTheme, type AppTheme } from '@core/theme';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatusBadgeProps {
  /** Status string (e.g. "approved", "rejected", "pending", "processing"). */
  status: string;
  /** Visual size of the badge. Defaults to "small". */
  size?: 'small' | 'medium';
}

// ---------------------------------------------------------------------------
// Status  ->  theme color mapping
// ---------------------------------------------------------------------------

type SemanticColorKey = 'success' | 'warning' | 'error' | 'info' | 'pending' | 'approved' | 'rejected' | 'processing';

/**
 * Resolves a freeform status string to the matching semantic color key.
 * Falls back to "info" for unknown statuses.
 */
function resolveColorKey(status: string): SemanticColorKey {
  const normalized = status.toLowerCase().replace(/[^a-z]/g, '');

  const mapping: Record<string, SemanticColorKey> = {
    approved: 'approved',
    accepted: 'approved',
    completed: 'success',
    active: 'success',
    rejected: 'rejected',
    failed: 'rejected',
    cancelled: 'rejected',
    expired: 'rejected',
    pending: 'pending',
    draft: 'pending',
    submitted: 'pending',
    warning: 'warning',
    processing: 'processing',
    inprogress: 'processing',
    locked: 'processing',
    review: 'processing',
  };

  return mapping[normalized] ?? 'info';
}

function getColors(colorKey: SemanticColorKey, themeColors: AppTheme['colors']) {
  switch (colorKey) {
    case 'approved':
    case 'success':
      return { bg: themeColors.approved, text: themeColors.onPrimary };
    case 'rejected':
    case 'error':
      return { bg: themeColors.rejected, text: themeColors.onError };
    case 'pending':
    case 'warning':
      return { bg: themeColors.pending, text: themeColors.onPrimary };
    case 'processing':
    case 'info':
    default:
      return { bg: themeColors.processing, text: themeColors.onTertiary };
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StatusBadge({ status, size = 'small' }: StatusBadgeProps) {
  const { colors, borderRadius } = useAppTheme();

  const colorKey = resolveColorKey(status);
  const { bg, text } = getColors(colorKey, colors);

  const isSmall = size === 'small';

  return (
    <Chip
      mode="flat"
      compact={isSmall}
      textStyle={[
        { color: text, fontSize: isSmall ? 11 : 13, fontWeight: '600' },
      ]}
      style={[
        styles.chip,
        {
          backgroundColor: bg,
          borderRadius: borderRadius.sm,
          height: isSmall ? 24 : 30,
        },
      ]}
    >
      {status}
    </Chip>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
  },
});
