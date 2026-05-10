/**
 * Collect Payment Screen — Cash or mobile money in field
 */

import React, { useCallback, useRef, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, RadioButton, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import {
  extractApiError,
  isPermissionError,
  isRateLimitError,
  getRetryAfterSeconds,
} from '@core/api/errors';
import { useNetwork } from '@core/hooks/use-network';
import { generateIdempotencyKey } from '@core/api/idempotency';
import { hapticSuccess, hapticError } from '@core/utils/haptics';
import { formatCurrency } from '@core/utils/format';
import { appConfig } from '@core/config/app';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useInspectionDetail, useInspectionObligations, useCollectPayment } from '@modules/inspections/services/inspections-hooks';
import { ObligationList } from '@modules/inspections/components/obligation-list';

export default function CollectPaymentScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { agentContext } = useAuth();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const { data: obligations, isLoading: obligationsLoading } = useInspectionObligations(
    inspection?.license_id,
  );

  // P4: Stable Idempotency-Key for the whole screen lifetime.
  // A retry (screen re-render, network blip) reuses the same key → server replay,
  // preventing double-charge (OWASP A04).
  const idempotencyKeyRef = useRef<string>(generateIdempotencyKey());
  const collectMutation = useCollectPayment(id ?? '', idempotencyKeyRef.current);

  // P4: Hard block on offline — no local queue for field payments (user decision).
  // The agent must wait for network before collecting cash. Safer than sync-risk.
  const { isConnected } = useNetwork();

  const [selectedObligations, setSelectedObligations] = useState<Set<string>>(new Set());
  const [method, setMethod] = useState<'cash' | 'mobile_money'>('cash');
  const [amount, setAmount] = useState('');
  const [phone, setPhone] = useState<string>(appConfig.business.phonePrefix);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  const toggleObligation = (obId: string) => {
    setSelectedObligations((prev) => {
      const next = new Set(prev);
      if (next.has(obId)) next.delete(obId);
      else next.add(obId);
      return next;
    });
  };

  const parsedAmount = Math.round(parseFloat(amount.replace(/[^0-9]/g, '')));

  // P4 lint fix: hooks must be called in the same order every render.
  // handleSubmit is declared BEFORE the early return so useCallback is
  // always invoked (react-hooks/rules-of-hooks).
  const handleSubmit = useCallback(() => {
    if (selectedObligations.size === 0) {
      setError(t('med.selectObligations'));
      return;
    }
    if (isNaN(parsedAmount) || parsedAmount <= 0) {
      setError(t('payment.invalidAmount'));
      return;
    }
    if (parsedAmount > appConfig.business.maxFieldCollectionAmount) {
      setError(t('payment.maxAmount', { amount: formatCurrency(appConfig.business.maxFieldCollectionAmount) }));
      return;
    }
    if (method === 'mobile_money' && !appConfig.business.phoneRegex.test(phone)) {
      setError(t('payment.invalidPhone'));
      return;
    }

    Alert.alert(
      t('payment.collect'),
      `${t('payment.method')}: ${t(`payment.${method}`)}\n${t('payment.amount')}: ${formatCurrency(parsedAmount)}`,
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('payment.confirm'),
          onPress: async () => {
            try {
              setError('');
              hapticSuccess();
              await collectMutation.mutateAsync({
                obligation_ids: Array.from(selectedObligations),
                method,
                amount: parsedAmount,
                phone_number: method === 'mobile_money' ? phone : undefined,
                notes: notes.trim() || undefined,
              });
              router.back();
            } catch (err) {
              hapticError();
              // P4: specialised error handling (403 out-of-scope, 429 rate limit)
              if (isPermissionError(err)) {
                const apiError = extractApiError(err);
                setError(t('collect.errorOutOfScope', {
                  defaultValue: apiError.message || 'Action not allowed by agent scope',
                }));
              } else if (isRateLimitError(err)) {
                const retrySeconds = getRetryAfterSeconds(err);
                setError(t('collect.errorRateLimit', {
                  defaultValue: `Too many attempts. Retry in ${retrySeconds}s`,
                  seconds: retrySeconds,
                }));
              } else {
                setError(extractApiError(err).message);
              }
            }
          },
        },
      ],
    );
  }, [selectedObligations, parsedAmount, method, phone, notes, collectMutation, t]);

  // P4 lint fix: early return AFTER all hooks
  if (isLoading || !inspection) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('payment.collect')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Company */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={{ color: colors.onSurface }}>
            {inspection.company_name ?? '—'}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {t('inspection.unpaidAmount')}: {formatCurrency(inspection.unpaid_obligations_amount)}
          </Text>
        </View>
        <Divider />

        {/* Obligations Selection */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('med.selectObligations')} ({selectedObligations.size} {t('med.selected')})
          </Text>
          {obligationsLoading ? (
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('common.loading')}
            </Text>
          ) : obligations && obligations.length > 0 ? (
            <ObligationList
              obligations={obligations}
              selectable
              selected={selectedObligations}
              onToggle={toggleObligation}
            />
          ) : (
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('obligations.none')}
            </Text>
          )}
        </View>
        <Divider />

        {/* Payment Method */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('payment.method')}
          </Text>
          <RadioButton.Group onValueChange={(v) => setMethod(v as 'cash' | 'mobile_money')} value={method}>
            <RadioButton.Item label={t('payment.cash')} value="cash" mode="android" />
            <RadioButton.Item label={t('payment.mobileMoney')} value="mobile_money" mode="android" />
          </RadioButton.Group>
        </View>
        <Divider />

        {/* Amount */}
        <View style={styles.section}>
          <TextInput
            mode="flat"
            label={`${t('payment.amount')} (XAF)`}
            value={amount}
            onChangeText={setAmount}
            keyboardType="numeric"
            style={{ backgroundColor: 'transparent' }}
          />
        </View>
        <Divider />

        {/* Phone (mobile_money only) */}
        {method === 'mobile_money' && (
          <>
            <View style={styles.section}>
              <TextInput
                mode="flat"
                label={t('payment.phone')}
                value={phone}
                onChangeText={setPhone}
                keyboardType="phone-pad"
                maxLength={20}
                style={{ backgroundColor: 'transparent' }}
              />
            </View>
            <Divider />
          </>
        )}

        {/* Notes */}
        <View style={styles.section}>
          <TextInput
            mode="flat"
            label={t('inspection.notes')}
            value={notes}
            onChangeText={setNotes}
            multiline
            maxLength={500}
            style={{ backgroundColor: 'transparent' }}
          />
        </View>

        {error ? (
          <Text variant="bodyMedium" style={{ color: colors.error, paddingHorizontal: 16 }}>{error}</Text>
        ) : null}

        {/* P4: Offline warning — hard block without local queue (user decision). */}
        {isConnected === false && (
          <View style={styles.section}>
            <Text variant="bodyMedium" style={{ color: colors.error, fontWeight: '600' }}>
              {t('collect.offlineBlock', {
                defaultValue: 'No network — wait for connection before collecting a payment.',
              })}
            </Text>
          </View>
        )}

        {/* Collection summary */}
        {selectedObligations.size > 0 && parsedAmount > 0 && (
          <View style={[styles.section, styles.summaryCard, { backgroundColor: `${colors.primary}08` }]}>
            <Text variant="labelMedium" style={{ color: colors.primary, fontWeight: '700' }}>
              {t('payment.summary', { defaultValue: 'Summary' })}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 4 }}>
              {selectedObligations.size} {t('obligations.title', { defaultValue: 'obligations' })} — {formatCurrency(parsedAmount)}
            </Text>
            {agentContext && (
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {agentContext.entityCode} — {agentContext.locationCity} ({agentContext.locationRegion})
              </Text>
            )}
          </View>
        )}

        <View style={styles.submitSection}>
          <Button
            mode="contained"
            icon="cash"
            onPress={handleSubmit}
            loading={collectMutation.isPending}
            disabled={collectMutation.isPending || !amount || isConnected === false}
            style={styles.submitButton}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('payment.confirm')} {parsedAmount > 0 ? formatCurrency(parsedAmount) : ''}
          </Button>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  content: { paddingBottom: 32 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 4 },
  summaryCard: { borderRadius: 8, marginHorizontal: 16, marginTop: 8 },
  submitSection: { paddingHorizontal: 16, paddingTop: 16 },
  submitButton: { borderRadius: 8 },
});
