/**
 * RetryPaymentSheet — modal that lets the citizen re-initiate a payment for an
 * existing service request after a failed/cancelled/abandoned attempt.
 *
 * Web parity: same workflow as `dashboard/service-requests/[id]` "Retry payment".
 *
 * Backend wiring:
 *   GET  /service-requests/{id}/payment/methods   -> list of active methods
 *   POST /service-requests/{id}/payment/initiate  -> redirect_url | agent_validation
 *
 * The list of methods is built dynamically by the backend's
 * `payment_processor_registry`, so this component never hardcodes the catalogue
 * (and stays correct when a new processor — e.g. card — is enabled in prod).
 */

import { useEffect, useMemo, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Button,
  Modal,
  Portal,
  RadioButton,
  Text,
  TextInput,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import {
  useRequestPaymentMethods,
  useRetryRequestPayment,
  type PaymentMethod,
  type RequestPaymentMethodInfo,
} from '@modules/payments';
import { getCurrentLanguage } from '@core/i18n';

interface Props {
  visible: boolean;
  onDismiss: () => void;
  serviceRequestId: string;
  /** Called with the result so the parent can show snackbars / refetch. */
  onResult: (outcome:
    | { kind: 'redirect'; url: string }
    | { kind: 'agent_validation'; messageKey: 'cash' | 'check' | 'generic' }
    | { kind: 'error'; message: string }
  ) => void;
}

function methodLabel(m: RequestPaymentMethodInfo): string {
  const lang = getCurrentLanguage();
  if (lang === 'fr') return m.label_fr;
  if (lang === 'en') return m.label_en;
  return m.label_es;
}

function methodIconHint(m: PaymentMethod): string {
  switch (m) {
    case 'mobile_money':
      return 'cellphone';
    case 'card':
      return 'credit-card-outline';
    case 'bank_transfer':
      return 'bank-transfer';
    case 'cash':
      return 'cash';
    case 'check':
      return 'checkbook';
    default:
      return 'currency-usd';
  }
}

export function RetryPaymentSheet({
  visible,
  onDismiss,
  serviceRequestId,
  onResult,
}: Props) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const methodsQuery = useRequestPaymentMethods(serviceRequestId, visible);
  const retry = useRetryRequestPayment();

  const [selected, setSelected] = useState<PaymentMethod | null>(null);
  const [phone, setPhone] = useState('');

  // Default-select either the backend default_method or the first method in the list.
  useEffect(() => {
    if (!visible) return;
    if (selected) return;
    const data = methodsQuery.data;
    if (!data) return;
    const def = data.default_method ?? data.methods[0]?.code ?? null;
    if (def) setSelected(def);
  }, [visible, methodsQuery.data, selected]);

  // Reset on close so re-open starts fresh.
  useEffect(() => {
    if (visible) return;
    setSelected(null);
    setPhone('');
  }, [visible]);

  const selectedMethod = useMemo<RequestPaymentMethodInfo | undefined>(
    () => methodsQuery.data?.methods.find((m) => m.code === selected) ?? undefined,
    [methodsQuery.data, selected],
  );

  const phoneRequired = selectedMethod?.requires_phone === true;
  const phoneValid = !phoneRequired || phone.trim().length >= 8;
  const canSubmit = !!selectedMethod && phoneValid && !retry.isPending;

  const handleSubmit = async () => {
    if (!selectedMethod) return;
    try {
      const res = await retry.mutateAsync({
        serviceRequestId,
        body: {
          payment_method: selectedMethod.code,
          ...(phoneRequired ? { phone_number: phone.trim() } : {}),
        },
      });
      if (res.redirect_url) {
        onResult({ kind: 'redirect', url: res.redirect_url });
        onDismiss();
        // Open the BANGE redirect in the system browser. Deep-linking back
        // is handled by `app/_layout.tsx` (deep-link router).
        await Linking.openURL(res.redirect_url);
        return;
      }
      if (res.action_type === 'agent_validation') {
        const messageKey: 'cash' | 'check' | 'generic' =
          selectedMethod.code === 'cash' ? 'cash'
          : selectedMethod.code === 'check' ? 'check'
          : 'generic';
        onResult({ kind: 'agent_validation', messageKey });
        onDismiss();
        return;
      }
      onResult({ kind: 'error', message: t('payments.retry.unknownResponse') });
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.error');
      onResult({ kind: 'error', message });
    }
  };

  return (
    <Portal>
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        contentContainerStyle={[
          styles.modal,
          {
            backgroundColor: colors.surface,
            borderRadius: borderRadius.md,
            padding: spacing.md,
          },
        ]}
      >
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', marginBottom: spacing.sm }}
        >
          {t('payments.retry.title')}
        </Text>
        <Text
          variant="bodySmall"
          style={{ color: colors.onSurfaceVariant, marginBottom: spacing.md }}
        >
          {t('payments.retry.subtitle')}
        </Text>

        {methodsQuery.isLoading ? (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={colors.primary} />
          </View>
        ) : methodsQuery.isError || !methodsQuery.data ? (
          <Text
            variant="bodySmall"
            style={{ color: colors.error, marginBottom: spacing.md }}
          >
            {t('payments.retry.methodsLoadError')}
          </Text>
        ) : (
          <RadioButton.Group
            onValueChange={(v) => setSelected(v as PaymentMethod)}
            value={selected ?? ''}
          >
            {methodsQuery.data.methods.map((m) => (
              <RadioButton.Item
                key={m.code}
                label={methodLabel(m)}
                value={m.code}
                position="trailing"
                style={styles.radioItem}
                accessibilityLabel={`${methodLabel(m)} (${methodIconHint(m.code)})`}
              />
            ))}
          </RadioButton.Group>
        )}

        {phoneRequired ? (
          <TextInput
            mode="outlined"
            label={t('payments.retry.phoneLabel')}
            placeholder="240XXXXXXXXX"
            keyboardType="phone-pad"
            value={phone}
            onChangeText={setPhone}
            style={{ marginTop: spacing.sm }}
            autoCorrect={false}
          />
        ) : null}

        <View style={[styles.actionsRow, { marginTop: spacing.md }]}>
          <Button onPress={onDismiss} disabled={retry.isPending}>
            {t('common.cancel')}
          </Button>
          <Button
            mode="contained"
            onPress={handleSubmit}
            disabled={!canSubmit}
            loading={retry.isPending}
            style={{ marginLeft: spacing.sm }}
          >
            {t('payments.retry.submit')}
          </Button>
        </View>
      </Modal>
    </Portal>
  );
}

const styles = StyleSheet.create({
  modal: { marginHorizontal: 16 },
  loadingRow: { paddingVertical: 24, alignItems: 'center' },
  radioItem: { paddingVertical: 0 },
  actionsRow: { flexDirection: 'row', justifyContent: 'flex-end' },
});
