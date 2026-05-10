/**
 * Request List Item — Native Android Style
 *
 * Compact 2-line list item matching Material Design 3 list pattern:
 * Line 1: Status dot + Workflow label ............... Status text
 * Line 2: Reference · Date relative ................ Amount
 *
 * No card elevation — uses flat layout with dividers (parent manages dividers).
 * Height ~60dp for native Android feel.
 */

import { View, StyleSheet, Pressable } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatRelativeTime, formatCurrency } from '@core/utils/format';
import type { ServiceRequestListItem } from '../types/requests.types';

interface RequestListItemProps {
  item: ServiceRequestListItem;
  onPress: () => void;
}

/** WORKFLOW_CODE → readable label */
function humanizeWorkflowCode(code: string): string {
  return code
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Status → dot color */
function getStatusDotColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'DRAFT': return '#9E9E9E';
    case 'SUBMITTED': return '#4CAF50';
    case 'PROCESSING':
    case 'UNDER_REVIEW': return '#FF9800';
    case 'PAYMENT_PENDING': return '#FFC107';
    case 'PAID': return '#2196F3';
    case 'COMPLETED':
    case 'VALIDATED': return '#1B5E20';
    case 'REJECTED': return '#F44336';
    case 'CANCELLED':
    case 'EXPIRED': return '#9E9E9E';
    case 'PENDING_DOCUMENTS': return '#9C27B0';
    default: return '#9E9E9E';
  }
}

/** Status → text color */
function getStatusTextColor(status: string): string {
  switch (status.toUpperCase()) {
    case 'DRAFT': return '#757575';
    case 'SUBMITTED': return '#2E7D32';
    case 'PROCESSING':
    case 'UNDER_REVIEW': return '#E65100';
    case 'PAYMENT_PENDING': return '#F57F17';
    case 'PAID': return '#1565C0';
    case 'COMPLETED':
    case 'VALIDATED': return '#1B5E20';
    case 'REJECTED': return '#C62828';
    case 'CANCELLED':
    case 'EXPIRED': return '#757575';
    case 'PENDING_DOCUMENTS': return '#7B1FA2';
    default: return '#757575';
  }
}

/** Humanize status for display */
function getStatusLabel(status: string, t: (key: string) => string): string {
  const i18nKey = `requests.status.${status.toLowerCase()}`;
  const translated = t(i18nKey);
  if (translated === i18nKey) {
    return status.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return translated;
}

export function RequestListItem({ item, onPress }: RequestListItemProps) {
  const { colors, spacing } = useAppTheme();
  const { t } = useTranslation();

  const dotColor = getStatusDotColor(item.status);
  const statusColor = getStatusTextColor(item.status);
  const statusLabel = getStatusLabel(item.status, t);
  const title = item.workflow_label || humanizeWorkflowCode(item.workflow_code);
  const timeAgo = formatRelativeTime(item.updated_at || item.created_at);

  return (
    <Pressable
      onPress={onPress}
      android_ripple={{ color: colors.primaryContainer }}
      style={[styles.container, { paddingHorizontal: spacing.md, paddingVertical: 12 }]}
    >
      {/* Status dot */}
      <View style={[styles.dot, { backgroundColor: dotColor }]} />

      {/* Content */}
      <View style={styles.content}>
        {/* Line 1: Title + Status label */}
        <View style={styles.line1}>
          <Text
            variant="bodyLarge"
            style={[styles.title, { color: colors.onSurface }]}
            numberOfLines={1}
          >
            {title}
          </Text>
          <Text
            style={[styles.statusText, { color: statusColor }]}
            numberOfLines={1}
          >
            {statusLabel}
          </Text>
        </View>

        {/* Line 2: Reference · Date | Amount */}
        <View style={styles.line2}>
          <Text
            variant="bodySmall"
            style={{ color: colors.outline, flex: 1 }}
            numberOfLines={1}
          >
            {item.reference} · {timeAgo}
          </Text>
          {item.total_amount != null && item.total_amount > 0 && (
            <Text style={[styles.amount, { color: colors.onSurface }]}>
              {formatCurrency(item.total_amount)}
            </Text>
          )}
        </View>
      </View>

      {/* Chevron */}
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
  container: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    marginRight: 12,
  },
  content: {
    flex: 1,
    gap: 2,
  },
  line1: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  title: {
    fontWeight: '600',
    flex: 1,
    fontSize: 15,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  line2: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  amount: {
    fontSize: 13,
    fontWeight: '600',
    marginLeft: 8,
  },
});
