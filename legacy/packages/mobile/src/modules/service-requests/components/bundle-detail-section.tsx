/**
 * BundleDetailSection — citizen-facing breakdown for SR of type BUNDLE_PAYMENT.
 *
 * Mirrors the web /dashboard/service-requests/[id] view (debug/tesoro/s.png):
 *
 *   ┌── Total / Pagado / Restante ──┐  ← 3 KPI cards
 *   ├── Card per entity ───────────┤  ← Ayuntamiento / Cámara / Tesoro,
 *   │     amount + status + receipt   │   each with method-coloured stripe
 *   ├── Obligaciones pagadas ──────┤  ← collapsible list
 *   └── Obligaciones pendientes ───┘
 *
 * Backend payload: `bundle_details` field on
 * GET /service-requests/{id}/detail-view (built at routes.py:1785). Driven
 * entirely by props — the component does not fetch.
 *
 * Visual decisions:
 * - KPI cards are tinted (primaryContainer / tertiaryContainer / errorContainer)
 *   so the user reads totals at a glance even on a low-DPI 5" device.
 * - Entity cards use a left status dot rather than a Chip — saves vertical
 *   space and matches the native list pattern used elsewhere (req detail).
 * - Obligation rows are flat (no Card per row) to keep the screen scannable.
 */

import { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, Divider } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import type {
  BundleDetails,
  BundlePaymentSplit,
  BundleObligationDetail,
} from '../types/requests.types';

interface Props {
  details: BundleDetails;
}

/**
 * payment_workflow_status values that count as "fully paid" for the KPI sum.
 * `completed` and `validated` are terminal-success; everything else is in
 * flight or refused.
 */
const PAID_PAYMENT_STATUSES = new Set([
  'completed',
  'validated',
  'paid',
]);

/** license_obligation statuses that count as "fully paid" for the list split. */
const PAID_OBLIGATION_STATUSES = new Set(['paid']);

function paymentStatusColor(
  status: string | null,
  colors: ReturnType<typeof useAppTheme>['colors'],
) {
  if (!status) return colors.outline;
  if (PAID_PAYMENT_STATUSES.has(status)) return colors.tertiary;
  if (status === 'failed' || status === 'rejected' || status === 'cancelled') return colors.error;
  return colors.primary; // pending / processing / locked / submitted
}

function obligationStatusColor(
  status: string,
  colors: ReturnType<typeof useAppTheme>['colors'],
) {
  if (PAID_OBLIGATION_STATUSES.has(status)) return colors.tertiary;
  if (status === 'overdue') return colors.error;
  return colors.primary;
}

function EntityCard({ split }: { split: BundlePaymentSplit }) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const dotColor = paymentStatusColor(split.status, colors);
  const statusLabel = split.status
    ? t(`requests.bundle.paymentStatus.${split.status}`, { defaultValue: split.status })
    : '—';
  return (
    <View
      style={[
        styles.entityCard,
        { backgroundColor: colors.surface, borderColor: colors.outlineVariant },
      ]}
    >
      <View style={[styles.entityStatusDot, { backgroundColor: dotColor }]} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text
          variant="labelSmall"
          numberOfLines={1}
          style={{ color: colors.onSurfaceVariant, textTransform: 'uppercase', letterSpacing: 0.5 }}
        >
          {split.entity_name ?? split.entity_code ?? '—'}
        </Text>
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '700' }}
        >
          {formatCurrency(split.amount, 'XAF')}
        </Text>
        <View style={styles.entityFooter}>
          <Text variant="labelSmall" style={{ color: dotColor, fontWeight: '600' }}>
            {statusLabel}
          </Text>
          {split.receipt_number ? (
            <Text
              variant="labelSmall"
              numberOfLines={1}
              style={{ color: colors.onSurfaceVariant }}
            >
              · {split.receipt_number}
            </Text>
          ) : null}
        </View>
      </View>
    </View>
  );
}

function ObligationRow({
  obligation,
  paid,
}: {
  obligation: BundleObligationDetail;
  paid: boolean;
}) {
  const { colors } = useAppTheme();
  const color = paid ? colors.tertiary : obligationStatusColor(obligation.status, colors);
  return (
    <View style={styles.obligationRow}>
      <MaterialCommunityIcons
        name={paid ? 'check-circle' : 'circle-outline'}
        size={16}
        color={color}
      />
      <Text
        variant="bodyMedium"
        numberOfLines={1}
        style={{ color: colors.onSurface, flex: 1, marginLeft: 8 }}
      >
        {obligation.service_name}
      </Text>
      <Text
        variant="bodyMedium"
        style={{ color: colors.onSurface, fontWeight: '600' }}
      >
        {formatCurrency(obligation.amount, 'XAF')}
      </Text>
    </View>
  );
}

export function BundleDetailSection({ details }: Props) {
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();

  // Split obligations into paid / pending so the screen reads at a glance.
  const { paidObligations, pendingObligations, paidAmount, remainingAmount } =
    useMemo(() => {
      const paidObl: BundleObligationDetail[] = [];
      const pendingObl: BundleObligationDetail[] = [];
      let paid = 0;
      for (const o of details.obligations) {
        if (PAID_OBLIGATION_STATUSES.has(o.status)) {
          paidObl.push(o);
          paid += o.amount;
        } else {
          pendingObl.push(o);
        }
      }
      return {
        paidObligations: paidObl,
        pendingObligations: pendingObl,
        paidAmount: paid,
        remainingAmount: Math.max(0, details.total_amount - paid),
      };
    }, [details.obligations, details.total_amount]);

  return (
    <View style={[styles.root, { paddingHorizontal: spacing.md }]}>
      {/* Company header */}
      <View style={styles.companyHeader}>
        <MaterialCommunityIcons
          name="domain"
          size={18}
          color={colors.onSurfaceVariant}
        />
        <Text
          variant="titleSmall"
          style={{ color: colors.onSurface, fontWeight: '700', marginLeft: 6 }}
          numberOfLines={1}
        >
          {details.company_name ?? '—'}
        </Text>
        {details.registration_number ? (
          <Text
            variant="labelSmall"
            style={{ color: colors.onSurfaceVariant, marginLeft: 8 }}
          >
            {details.registration_number}
          </Text>
        ) : null}
      </View>

      {/* KPI row — Total / Paid / Remaining */}
      <View style={styles.kpiRow}>
        <View style={[styles.kpiCard, { backgroundColor: colors.surfaceVariant }]}>
          <Text variant="labelSmall" style={styles.kpiLabel}>
            {t('requests.bundle.total')}
          </Text>
          <Text
            variant="titleMedium"
            style={[styles.kpiValue, { color: colors.onSurface }]}
            numberOfLines={1}
          >
            {formatCurrency(details.total_amount, 'XAF')}
          </Text>
        </View>
        <View style={[styles.kpiCard, { backgroundColor: '#E8F5E9' }]}>
          <Text variant="labelSmall" style={[styles.kpiLabel, { color: '#1B5E20' }]}>
            {t('requests.bundle.paid')}
          </Text>
          <Text
            variant="titleMedium"
            style={[styles.kpiValue, { color: '#1B5E20' }]}
            numberOfLines={1}
          >
            {formatCurrency(paidAmount, 'XAF')}
          </Text>
        </View>
        <View style={[styles.kpiCard, { backgroundColor: '#FFEBEE' }]}>
          <Text variant="labelSmall" style={[styles.kpiLabel, { color: '#B71C1C' }]}>
            {t('requests.bundle.remaining')}
          </Text>
          <Text
            variant="titleMedium"
            style={[styles.kpiValue, { color: '#B71C1C' }]}
            numberOfLines={1}
          >
            {formatCurrency(remainingAmount, 'XAF')}
          </Text>
        </View>
      </View>

      {/* Entity split cards — Ayuntamiento / Cámara / Tesoro */}
      {details.splits.length > 0 ? (
        <View style={styles.entityGrid}>
          {details.splits.map((s, i) => (
            <EntityCard key={`${s.entity_code ?? 'split'}-${i}`} split={s} />
          ))}
        </View>
      ) : null}

      {/* Paid obligations list */}
      {paidObligations.length > 0 ? (
        <View style={styles.section}>
          <Text variant="labelLarge" style={{ color: colors.tertiary, fontWeight: '700' }}>
            {t('requests.bundle.paidObligations', { count: paidObligations.length })}
          </Text>
          <View style={{ marginTop: 6 }}>
            {paidObligations.map((o, i) => (
              <View key={`paid-${i}`}>
                {i > 0 ? <Divider style={{ marginVertical: 4 }} /> : null}
                <ObligationRow obligation={o} paid />
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {/* Pending obligations list */}
      {pendingObligations.length > 0 ? (
        <View style={styles.section}>
          <Text variant="labelLarge" style={{ color: colors.primary, fontWeight: '700' }}>
            {t('requests.bundle.pendingObligations', { count: pendingObligations.length })}
          </Text>
          <View style={{ marginTop: 6 }}>
            {pendingObligations.map((o, i) => (
              <View key={`pending-${i}`}>
                {i > 0 ? <Divider style={{ marginVertical: 4 }} /> : null}
                <ObligationRow obligation={o} paid={false} />
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { gap: 12, paddingTop: 12, paddingBottom: 8 },
  companyHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  kpiRow: {
    flexDirection: 'row',
    gap: 8,
  },
  kpiCard: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 10,
    alignItems: 'center',
  },
  kpiLabel: {
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    fontWeight: '600',
  },
  kpiValue: { fontWeight: '700', marginTop: 2 },
  entityGrid: { gap: 8 },
  entityCard: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
  },
  entityStatusDot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  entityFooter: { flexDirection: 'row', alignItems: 'center', gap: 4, flexWrap: 'wrap' },
  section: { marginTop: 4 },
  obligationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
  },
});
