/**
 * Payment Status Badge — coloured pill for payment_status_enum values.
 */

import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme, type AppTheme } from '@core/theme';
import type { PaymentStatus } from '../types/payments.types';

interface PaymentStatusBadgeProps {
  status: PaymentStatus;
  compact?: boolean;
}

type BadgeColors = { bg: string; text: string };

function getColors(
  status: PaymentStatus,
  colors: AppTheme['colors'],
  isDark: boolean,
): BadgeColors {
  // Dark-mode palette — desaturated background + bright on-surface text
  // (verified ≥ 4.5:1 contrast against the dark surface tokens).
  if (isDark) {
    switch (status) {
      case 'pending':
        return { bg: '#3E2C00', text: '#FFCC80' };
      case 'processing':
        return { bg: '#3E2200', text: '#FFB74D' };
      case 'completed':
        return { bg: '#1B3320', text: '#A5D6A7' };
      case 'failed':
        return { bg: '#3E1A1A', text: '#EF9A9A' };
      case 'cancelled':
        return { bg: colors.surfaceVariant, text: colors.outline };
      case 'refunded':
        return { bg: '#0D2440', text: '#90CAF9' };
      default:
        return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
    }
  }
  // Light-mode palette — pastel background + dark accent text (≥ 4.5:1).
  switch (status) {
    case 'pending':
      return { bg: '#FFF8E1', text: '#7A4F00' };
    case 'processing':
      return { bg: '#FFF3E0', text: '#7A2E00' };
    case 'completed':
      return { bg: '#E8F5E9', text: '#1B5E20' };
    case 'failed':
      return { bg: '#FFEBEE', text: '#8B1A1A' };
    case 'cancelled':
      return { bg: colors.surfaceVariant, text: colors.outline };
    case 'refunded':
      return { bg: '#E3F2FD', text: '#0D3D6B' };
    default:
      return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
  }
}

export function PaymentStatusBadge({ status, compact }: PaymentStatusBadgeProps) {
  const { colors, isDark } = useAppTheme();
  const { t } = useTranslation();
  const badge = getColors(status, colors, isDark);
  const label = t(`payments.status.${status}`, {
    defaultValue: status.charAt(0).toUpperCase() + status.slice(1),
  });

  return (
    <View
      style={[
        styles.badge,
        compact ? styles.compact : styles.normal,
        { backgroundColor: badge.bg },
      ]}
    >
      <Text
        style={[compact ? styles.textCompact : styles.textNormal, { color: badge.text }]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', borderRadius: 20 },
  normal: { paddingHorizontal: 12, paddingVertical: 5 },
  compact: { paddingHorizontal: 8, paddingVertical: 3 },
  textNormal: { fontSize: 12, fontWeight: '600', lineHeight: 16 },
  textCompact: { fontSize: 10, fontWeight: '600', lineHeight: 14 },
});
