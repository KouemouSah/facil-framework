/**
 * Citizen "Mis Empresas" card.
 *
 * Wired on `MyCompanyStatusItem` returned by GET /bundle-workflow/my-companies.
 * Shows registration_number, license_status (colored dot), deadline, and a
 * "Pay" CTA when there are pending obligations.
 */

import React, { memo, useCallback } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { MyCompanyStatusItem } from '../types/bundles.types';

interface BundleCompanyCardProps {
  item: MyCompanyStatusItem;
  onPress: (item: MyCompanyStatusItem) => void;
  onPay?: (item: MyCompanyStatusItem) => void;
}

function statusDot(status: string | null, colors: ReturnType<typeof useAppTheme>['colors']) {
  switch (status) {
    case 'active':
      return colors.tertiary; // green-ish in MD3 default
    case 'pending_payment':
    case 'draft':
      return colors.primary;
    case 'expired':
    case 'revoked':
    case 'cancelled':
      return colors.error;
    default:
      return colors.outline;
  }
}

function BundleCompanyCardImpl({ item, onPress, onPay }: BundleCompanyCardProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { company, license_status, pending_obligations } = item;

  const dotColor = statusDot(license_status, colors);
  const statusLabel = license_status
    ? t(`companies.license.status.${license_status}`, { defaultValue: license_status })
    : t('companies.card.noLicense');

  const obligations = pending_obligations || 0;
  const obligationsText =
    obligations > 0
      ? t('companies.card.pendingObligations', { count: obligations })
      : t('companies.card.noPending');

  const handlePay = useCallback(() => onPay?.(item), [item, onPay]);

  return (
    <Pressable
      onPress={() => onPress(item)}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[styles.row, { backgroundColor: colors.surface }]}
    >
      <View style={[styles.iconWrap, { backgroundColor: `${colors.primary}1A` }]}>
        <MaterialCommunityIcons name="domain" size={24} color={colors.primary} />
      </View>

      <View style={styles.body}>
        <Text
          variant="titleSmall"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: '600' }}
        >
          {company.legal_name}
        </Text>

        <View style={styles.metaRow}>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
            {company.registration_number
              ? `${t('companies.card.registrationNumber')}: ${company.registration_number}`
              : (company.tax_id ?? company.nif ?? '—')}
          </Text>
        </View>

        <View style={styles.statusRow}>
          <View style={[styles.dot, { backgroundColor: dotColor }]} />
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
            {statusLabel}
          </Text>
          <Text
            variant="bodySmall"
            style={{ color: obligations > 0 ? colors.error : colors.onSurfaceVariant }}
          >
            {' · '}
            {obligationsText}
          </Text>
        </View>
      </View>

      {obligations > 0 && onPay ? (
        <Pressable
          onPress={handlePay}
          android_ripple={{ color: colors.onPrimary }}
          style={[styles.payBtn, { backgroundColor: colors.primary }]}
          accessibilityRole="button"
          accessibilityLabel={t('companies.card.pay')}
        >
          <Text style={{ color: colors.onPrimary, fontWeight: '700', fontSize: 13 }}>
            {t('companies.card.pay')}
          </Text>
        </Pressable>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 72,
    alignItems: 'center',
    gap: 12,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1, gap: 2 },
  metaRow: { flexDirection: 'row', alignItems: 'center' },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  payBtn: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
});

export const BundleCompanyCard = memo(BundleCompanyCardImpl);
