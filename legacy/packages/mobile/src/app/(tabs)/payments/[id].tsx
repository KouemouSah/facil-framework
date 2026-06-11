/**
 * Payment Detail Screen
 *
 * Breakdown of a single payment + status badge + receipt download (when the
 * vault holds a generated payment_receipt for this service request) +
 * navigation to the originating request.
 */

import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Card, Divider, IconButton, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { formatCurrency, formatDate } from '@core/utils/format';
import {
  PaymentStatusBadge,
  ReceiptDownloadButton,
  usePayment,
} from '@modules/payments';
import type { Payment } from '@modules/payments';

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  const { colors } = useAppTheme();
  if (!value) return null;
  return (
    <View style={styles.row}>
      <Text variant="bodyMedium" style={{ color: colors.outline, flex: 1 }}>
        {label}
      </Text>
      <Text
        variant="bodyMedium"
        style={{ color: colors.onSurface, fontWeight: '500', flexShrink: 0 }}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  );
}

function PaymentDetailContent({
  payment,
  serviceRequestId,
}: {
  payment: Payment;
  serviceRequestId: string | null;
}) {
  const { colors, spacing } = useAppTheme();
  const { t } = useTranslation();
  const router = useRouter();

  const methodLabel = t(`payments.method.${payment.payment_method}`, {
    defaultValue: payment.payment_method,
  });

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={[styles.scroll, { padding: spacing.md }]}
    >
      {/* Header card */}
      <Card style={[styles.card, { backgroundColor: colors.surface }]} mode="elevated">
        <Card.Content>
          <View style={styles.totalRow}>
            <Text variant="bodySmall" style={{ color: colors.outline }}>
              {t('payments.detail.total')}
            </Text>
            <PaymentStatusBadge status={payment.status} />
          </View>
          <Text variant="displaySmall" style={{ color: colors.onSurface, fontWeight: '700' }}>
            {formatCurrency(payment.amount, payment.currency)}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.outline, marginTop: 4 }}>
            {methodLabel}
          </Text>
        </Card.Content>
      </Card>

      {/* Breakdown */}
      <Card style={[styles.card, { backgroundColor: colors.surface }]} mode="elevated">
        <Card.Content>
          <Text variant="titleSmall" style={{ color: colors.onSurface, marginBottom: 8 }}>
            {t('payments.detail.breakdown')}
          </Text>
          <Row
            label={t('payments.detail.baseAmount')}
            value={formatCurrency(payment.base_amount, payment.currency)}
          />
          {payment.penalties > 0 ? (
            <Row
              label={t('payments.detail.penalties')}
              value={formatCurrency(payment.penalties, payment.currency)}
            />
          ) : null}
          {payment.interest > 0 ? (
            <Row
              label={t('payments.detail.interest')}
              value={formatCurrency(payment.interest, payment.currency)}
            />
          ) : null}
          <Divider style={{ marginVertical: 8 }} />
          <Row
            label={t('payments.detail.total')}
            value={formatCurrency(payment.amount, payment.currency)}
          />
        </Card.Content>
      </Card>

      {/* Metadata */}
      <Card style={[styles.card, { backgroundColor: colors.surface }]} mode="elevated">
        <Card.Content>
          <Row label={t('payments.detail.method')} value={methodLabel} />
          <Row label={t('payments.detail.reference')} value={payment.bank_reference} />
          <Row
            label={t('payments.detail.transactionId')}
            value={payment.bank_transaction_id}
          />
          <Row
            label={t('payments.detail.createdAt')}
            value={formatDate(payment.created_at)}
          />
          {payment.paid_at ? (
            <Row label={t('payments.detail.paidAt')} value={formatDate(payment.paid_at)} />
          ) : null}
        </Card.Content>
      </Card>

      {/* Actions */}
      <View style={{ gap: 12, marginTop: 8 }}>
        <ReceiptDownloadButton serviceRequestId={serviceRequestId} />
        {serviceRequestId ? (
          <Button
            mode="outlined"
            icon="file-document-outline"
            onPress={() => router.push(`/(tabs)/requests/${serviceRequestId}` as never)}
          >
            {t('payments.detail.viewRequest')}
          </Button>
        ) : null}
      </View>
    </ScrollView>
  );
}

// Strict UUIDv4-shaped (or any 36-char hex+dash) check — defends against
// open-redirect-style query injection on params we forward to API requests.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function PaymentDetailScreenContent() {
  const params = useLocalSearchParams<{ id: string; serviceRequestId?: string }>();
  const id = UUID_RE.test(params.id ?? '') ? (params.id as string) : '';
  // Service request ID is not exposed by `PaymentResponse`; the caller (request
  // detail screen, wizard payment-result) passes it as a query param so we can
  // resolve the receipt and the "View request" CTA. Validated to UUID shape
  // before being fed into any subsequent API request.
  const serviceRequestId =
    params.serviceRequestId && UUID_RE.test(params.serviceRequestId)
      ? params.serviceRequestId
      : null;
  const router = useRouter();
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const { data: payment, isLoading, error, refetch } = usePayment(id);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View style={[styles.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleSmall"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {t('payments.detail.title')}
        </Text>
      </View>

      {isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : error || !payment ? (
        <View style={styles.centered}>
          <MaterialCommunityIcons
            name="alert-circle-outline"
            size={48}
            color={colors.error}
          />
          <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12, textAlign: 'center', paddingHorizontal: 24 }}>
            {t('payments.detail.errorLoading')}
          </Text>
          <Button mode="contained" onPress={() => refetch()} style={{ marginTop: 16 }}>
            {t('common.retry')}
          </Button>
        </View>
      ) : (
        <PaymentDetailContent payment={payment} serviceRequestId={serviceRequestId} />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  scroll: { gap: 12 },
  card: { borderRadius: 12 },
  totalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    gap: 12,
  },
});

export default function PaymentDetailScreen() {
  return (
    <AuthGuard>
      <PaymentDetailScreenContent />
    </AuthGuard>
  );
}
