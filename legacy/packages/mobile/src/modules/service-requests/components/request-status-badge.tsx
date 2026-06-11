/**
 * Request Status Badge — Mobile-optimized
 *
 * Custom badge (not Paper Chip) designed for mobile readability:
 * - Larger text, proper padding
 * - High contrast colors for each status
 * - Rounded pill shape
 * - Truncates gracefully with ellipsis
 */

import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme, type AppTheme } from '@core/theme';

interface RequestStatusBadgeProps {
  status: string;
  /** Compact mode for tight layouts (smaller text) */
  compact?: boolean;
}

type BadgeColors = {
  bg: string;
  text: string;
};

function getStatusColors(status: string, colors: AppTheme['colors']): BadgeColors {
  switch (status.toUpperCase()) {
    case 'DRAFT':
      return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
    case 'SUBMITTED':
      return { bg: '#E8F5E9', text: '#2E7D32' }; // green light
    case 'PROCESSING':
    case 'UNDER_REVIEW':
      return { bg: '#FFF3E0', text: '#E65100' }; // orange
    case 'PAYMENT_PENDING':
      return { bg: '#FFF8E1', text: '#F57F17' }; // amber
    case 'PAID':
      return { bg: '#E3F2FD', text: '#1565C0' }; // blue
    case 'COMPLETED':
    case 'VALIDATED':
      return { bg: '#E8F5E9', text: '#1B5E20' }; // green dark
    case 'REJECTED':
      return { bg: '#FFEBEE', text: '#C62828' }; // red
    case 'CANCELLED':
    case 'EXPIRED':
      return { bg: colors.surfaceVariant, text: colors.outline };
    case 'PENDING_DOCUMENTS':
      return { bg: '#F3E5F5', text: '#7B1FA2' }; // purple
    default:
      return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
  }
}

/** Humanize unknown status codes */
function humanizeStatus(status: string): string {
  return status
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function RequestStatusBadge({ status, compact }: RequestStatusBadgeProps) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  const badgeColors = getStatusColors(status, colors);

  const i18nKey = `requests.status.${status.toLowerCase()}`;
  const translated = t(i18nKey);
  const label = translated === i18nKey ? humanizeStatus(status) : translated;

  return (
    <View
      style={[
        styles.badge,
        compact ? styles.badgeCompact : styles.badgeNormal,
        { backgroundColor: badgeColors.bg },
      ]}
    >
      <Text
        style={[
          compact ? styles.textCompact : styles.textNormal,
          { color: badgeColors.text },
        ]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    borderRadius: 20,
  },
  badgeNormal: {
    paddingHorizontal: 12,
    paddingVertical: 5,
  },
  badgeCompact: {
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  textNormal: {
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 16,
  },
  textCompact: {
    fontSize: 10,
    fontWeight: '600',
    lineHeight: 14,
  },
});
