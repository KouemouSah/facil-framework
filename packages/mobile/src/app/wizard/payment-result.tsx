/**
 * Payment Result Screen — wizard exit after BANGE checkout (deep link target).
 *
 * URL pattern: `facil://wizard/payment-result?session_id=...&service_request_id=...&payment_id=...&status=...`
 *
 * Behavior:
 * - Polls `GET /service-requests/{service_request_id}/payment/status` every 3s
 *   while the backend reports a non-terminal status.
 * - Stops automatically on `completed | failed | cancelled | refunded` or after
 *   100 attempts (~5 min) — caps the timeout safely.
 * - 5 UI states: loading initial, polling-in-progress, completed, failed, timeout.
 *
 * Backend route (already in place):
 *   `routes.py:1204` — `PaymentStatusResponse {status, paid, payment_id, amount, currency, payment_method, completed_at}`
 */

import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Button, Surface, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { usePaymentStatusPolling } from '@modules/payments';

const MAX_ATTEMPTS = 100;
const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = MAX_ATTEMPTS * POLL_INTERVAL_MS;

type UIPhase = 'loading' | 'polling' | 'completed' | 'failed' | 'timeout';

export default function PaymentResultScreen() {
  const params = useLocalSearchParams<{
    session_id?: string;
    service_request_id?: string;
    payment_id?: string;
    status?: string;
  }>();
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const serviceRequestId = params.service_request_id ?? null;

  const polling = usePaymentStatusPolling(serviceRequestId, {
    enabled: !!serviceRequestId,
    intervalMs: POLL_INTERVAL_MS,
    maxAttempts: MAX_ATTEMPTS,
  });

  // Independent fail-safe timeout: if backend never reports a terminal status
  // within ~5 min, switch to the "timeout" phase regardless of the polling hook.
  const [timedOut, setTimedOut] = useState(false);
  useEffect(() => {
    if (!serviceRequestId) return undefined;
    setTimedOut(false);
    const t = setTimeout(() => setTimedOut(true), POLL_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [serviceRequestId]);

  const phase: UIPhase = useMemo(() => {
    if (!serviceRequestId) {
      return params.status === 'failed' ? 'failed' : 'timeout';
    }
    const status = polling.data?.status;
    if (status === 'completed' || status === 'refunded') return 'completed';
    if (status === 'failed' || status === 'cancelled') return 'failed';
    if (timedOut) return 'timeout';
    if (polling.isLoading || !polling.data) return 'loading';
    return 'polling';
  }, [
    serviceRequestId,
    params.status,
    polling.isLoading,
    polling.data,
    timedOut,
  ]);

  const config = (() => {
    switch (phase) {
      case 'completed':
        return {
          icon: 'check-circle-outline' as const,
          color: '#1B5E20',
          title: t('payments.result.completed'),
        };
      case 'failed':
        return {
          icon: 'close-circle-outline' as const,
          color: colors.error,
          title: t('payments.result.failed'),
        };
      case 'timeout':
        return {
          icon: 'clock-alert-outline' as const,
          color: '#F57F17',
          title: t('payments.result.timeout'),
        };
      case 'polling':
        return {
          icon: 'progress-clock' as const,
          color: colors.primary,
          title: t('payments.result.processing'),
        };
      case 'loading':
      default:
        return {
          icon: 'progress-clock' as const,
          color: colors.primary,
          title: t('payments.result.checking'),
        };
    }
  })();

  const showSpinner = phase === 'loading' || phase === 'polling';
  const paymentId = polling.data?.payment_id ?? params.payment_id ?? null;

  const handleViewRequest = () => {
    if (!serviceRequestId) {
      router.replace('/(tabs)/requests' as never);
      return;
    }
    router.replace(`/(tabs)/requests/${serviceRequestId}` as never);
  };

  const handleViewPayment = () => {
    if (!paymentId) return;
    const target = serviceRequestId
      ? `/(tabs)/payments/${paymentId}?serviceRequestId=${serviceRequestId}`
      : `/(tabs)/payments/${paymentId}`;
    router.replace(target as never);
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.content, { padding: spacing.lg }]}>
        <Surface
          style={[
            styles.card,
            {
              padding: spacing.xl,
              borderRadius: borderRadius.lg,
              backgroundColor: colors.surface,
            },
          ]}
          elevation={1}
        >
          {showSpinner ? (
            <ActivityIndicator size="large" color={config.color} style={{ marginBottom: 12 }} />
          ) : (
            <MaterialCommunityIcons name={config.icon} size={72} color={config.color} />
          )}
          <Text
            variant="titleMedium"
            style={[styles.title, { color: colors.onSurface, marginTop: spacing.md }]}
          >
            {config.title}
          </Text>

          {phase === 'completed' ? (
            <View style={{ marginTop: spacing.lg, gap: 12, width: '100%' }}>
              {paymentId ? (
                <Button mode="contained" icon="receipt" onPress={handleViewPayment}>
                  {t('payments.result.viewReceipt')}
                </Button>
              ) : null}
              <Button mode="outlined" icon="file-document-outline" onPress={handleViewRequest}>
                {t('payments.result.viewRequest')}
              </Button>
            </View>
          ) : null}

          {phase === 'failed' ? (
            <View style={{ marginTop: spacing.lg, gap: 12, width: '100%' }}>
              <Button mode="contained" icon="refresh" onPress={() => polling.refetch()}>
                {t('payments.result.retry')}
              </Button>
              <Button mode="outlined" onPress={() => router.replace('/(tabs)' as never)}>
                {t('payments.result.goHome')}
              </Button>
            </View>
          ) : null}

          {phase === 'timeout' ? (
            <Button
              mode="outlined"
              style={{ marginTop: spacing.lg }}
              onPress={handleViewRequest}
            >
              {t('payments.result.viewRequest')}
            </Button>
          ) : null}
        </Surface>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  card: { alignItems: 'center', width: '100%', maxWidth: 420 },
  title: { fontWeight: '700', textAlign: 'center' },
});
