/**
 * Payment List Item — Native Android style flat list row.
 *
 * Mirrors the visual language of `RequestListItem`:
 * Line 1: Status dot + Title (method/workflow) ........... Status label
 * Line 2: Reference · Date relative ........................ Amount
 */

import { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatRelativeTime, formatCurrency } from '@core/utils/format';
import type { Payment, PaymentStatus } from '../types/payments.types';

interface PaymentListItemProps {
  item: Payment;
  /** Receives the payment id — keep this callback stable (useCallback) for `memo` to work. */
  onPress: (paymentId: string) => void;
}

function getStatusDotColor(status: PaymentStatus, isDark: boolean): string {
  // Dot uses bright/saturated colors on both schemes — small surface area, high glance value.
  switch (status) {
    case 'pending':
      return isDark ? '#FFCA28' : '#FFC107';
    case 'processing':
      return isDark ? '#FFA726' : '#FF9800';
    case 'completed':
      return isDark ? '#66BB6A' : '#1B5E20';
    case 'failed':
      return isDark ? '#EF5350' : '#F44336';
    case 'cancelled':
      return isDark ? '#BDBDBD' : '#9E9E9E';
    case 'refunded':
      return isDark ? '#42A5F5' : '#1565C0';
    default:
      return isDark ? '#BDBDBD' : '#9E9E9E';
  }
}

function getStatusTextColor(status: PaymentStatus, isDark: boolean): string {
  // Text contrast tuned ≥ 4.5:1 against the surface in each scheme.
  if (isDark) {
    switch (status) {
      case 'pending':
        return '#FFCC80';
      case 'processing':
        return '#FFB74D';
      case 'completed':
        return '#A5D6A7';
      case 'failed':
        return '#EF9A9A';
      case 'cancelled':
        return '#BDBDBD';
      case 'refunded':
        return '#90CAF9';
      default:
        return '#BDBDBD';
    }
  }
  switch (status) {
    case 'pending':
      return '#7A4F00';
    case 'processing':
      return '#7A2E00';
    case 'completed':
      return '#1B5E20';
    case 'failed':
      return '#8B1A1A';
    case 'cancelled':
      return '#616161';
    case 'refunded':
      return '#0D3D6B';
    default:
      return '#616161';
  }
}

function PaymentListItemImpl({ item, onPress }: PaymentListItemProps) {
  const { colors, spacing, isDark } = useAppTheme();
  const { t } = useTranslation();

  const dotColor = getStatusDotColor(item.status, isDark);
  const statusColor = getStatusTextColor(item.status, isDark);
  const statusLabel = t(`payments.status.${item.status}`, {
    defaultValue: item.status,
  });
  const methodLabel = t(`payments.method.${item.payment_method}`, {
    defaultValue: item.payment_method
      ? item.payment_method.replace(/_/g, ' ')
      : t('payments.unknownMethod', 'Pago'),
  });
  const title = item.fiscal_service_name || methodLabel;
  const reference = item.bank_reference || item.id.slice(0, 8);
  const timeAgo = formatRelativeTime(item.paid_at || item.created_at);

  const a11yLabel = t('payments.a11y.item', {
    title,
    status: statusLabel,
    amount: formatCurrency(item.amount, item.currency),
    defaultValue: `${title}, ${statusLabel}, ${formatCurrency(item.amount, item.currency)}`,
  });

  return (
    <Pressable
      onPress={() => onPress(item.id)}
      android_ripple={{ color: colors.primaryContainer }}
      accessibilityRole="button"
      accessibilityLabel={a11yLabel}
      style={[
        styles.container,
        { paddingHorizontal: spacing.md, paddingVertical: 12 },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: dotColor }]} />

      <View style={styles.content}>
        <View style={styles.line1}>
          <Text
            variant="bodyLarge"
            style={[styles.title, { color: colors.onSurface }]}
            numberOfLines={1}
          >
            {title}
          </Text>
          <Text style={[styles.statusText, { color: statusColor }]} numberOfLines={1}>
            {statusLabel}
          </Text>
        </View>

        <View style={styles.line2}>
          <Text
            variant="bodySmall"
            style={{ color: colors.outline, flex: 1 }}
            numberOfLines={1}
          >
            {reference} · {timeAgo}
          </Text>
          <Text style={[styles.amount, { color: colors.onSurface }]}>
            {formatCurrency(item.amount, item.currency)}
          </Text>
        </View>
      </View>

      <MaterialCommunityIcons
        name="chevron-right"
        size={20}
        color={colors.outline}
        style={{ marginLeft: 4 }}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  content: { flex: 1, gap: 2 },
  line1: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  title: { fontWeight: '600', flex: 1, fontSize: 15 },
  statusText: { fontSize: 12, fontWeight: '600' },
  line2: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  amount: { fontSize: 13, fontWeight: '600', marginLeft: 8 },
});

/**
 * Memoized — list re-renders on filter change or pagination land, but identity
 * of `item` and `onPress` is stable thanks to the parent's keyExtractor + useCallback.
 * Avoids re-rendering 20+ items on each scroll tick.
 */
export const PaymentListItem = memo(PaymentListItemImpl);
