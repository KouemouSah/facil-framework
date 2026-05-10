import { useState, useEffect, useCallback } from 'react';
import { StyleSheet, View, ScrollView } from 'react-native';
import { Text, Button, Divider, RadioButton, TextInput, ActivityIndicator, HelperText } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import * as WebBrowser from 'expo-web-browser';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import type {
  PreparePaymentResult,
  InitiatePaymentRequest,
  InitiatePaymentResult,
  PaymentMethod,
  ValidationError,
} from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepPaymentProps {
  /**
   * Optional — when provided, the wizard builds a `facil://wizard/payment-result`
   * deep link as the BANGE return_url so the user is brought back into the app
   * after Mobile Money checkout. Validated server-side against the
   * `MOBILE_DEEP_LINK_SCHEMES` whitelist + FRONTEND_URL origin.
   */
  sessionId?: string;
  preparePayment: () => Promise<PreparePaymentResult>;
  initiatePayment: (data: InitiatePaymentRequest) => Promise<InitiatePaymentResult>;
  isSaving: boolean;
  onPaymentComplete: (result: InitiatePaymentResult) => void;
}

/**
 * Build the deep link the backend should hand to BANGE as `return_url`.
 * `service_request_id` is appended after the call (we don't have it yet here).
 */
function buildReturnUrl(sessionId: string | undefined): string | undefined {
  if (!sessionId) return undefined;
  return `facil://wizard/payment-result?session_id=${encodeURIComponent(sessionId)}`;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const METHOD_ICONS: Record<string, string> = {
  mobile_money: 'cellphone',
  card: 'credit-card',
  cash: 'cash',
  bank_transfer: 'bank',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepPayment({
  sessionId,
  preparePayment,
  initiatePayment,
  isSaving,
  onPaymentComplete,
}: StepPaymentProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [prepareResult, setPrepareResult] = useState<PreparePaymentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [prepareError, setPrepareError] = useState<string | null>(null);

  // Selections
  const [selectedMethod, setSelectedMethod] = useState<string>('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [paying, setPaying] = useState(false);

  // ── Prepare payment on mount ───────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setPrepareError(null);
    preparePayment()
      .then((result) => {
        if (cancelled) return;
        setPrepareResult(result);
        if (result.default_payment_method) {
          setSelectedMethod(result.default_payment_method);
        } else if (result.payment_methods.length > 0) {
          setSelectedMethod(result.payment_methods[0].code);
        }
      })
      .catch(() => {
        if (!cancelled) setPrepareError(t('wizard.payment.errorPrepare'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [preparePayment, t]);

  // ── Derived state ──────────────────────────────────────────────────────
  const currentMethod: PaymentMethod | undefined = prepareResult?.payment_methods.find(
    (m) => m.code === selectedMethod,
  );
  const needsPhone = currentMethod?.requires_phone ?? false;
  const phoneValid = !needsPhone || /^(222|555|551|333)\d{6}$/.test(phoneNumber);
  const canPay =
    prepareResult?.ready_for_payment &&
    prepareResult.validation_passed &&
    selectedMethod !== '' &&
    phoneValid &&
    !paying &&
    !isSaving;

  // ── Initiate payment ───────────────────────────────────────────────────
  const handlePay = useCallback(async () => {
    if (!canPay) return;
    setPaying(true);
    try {
      const returnUrl = buildReturnUrl(sessionId);
      const request: InitiatePaymentRequest = {
        payment_method: selectedMethod,
        ...(needsPhone && phoneNumber ? { phone_number: phoneNumber } : {}),
        ...(returnUrl ? { return_url: returnUrl } : {}),
      };
      const result = await initiatePayment(request);
      // For BANGE Mobile Money flows the backend hands back a `redirect_url` to
      // the gateway. Open it in the in-app browser so it can hand control back
      // to us via the deep link `facil://wizard/payment-result?...`. For cash /
      // check / bank transfer there's no redirect — fall straight through.
      if (result.success && result.redirect_url) {
        try {
          await WebBrowser.openBrowserAsync(result.redirect_url);
        } catch {
          // Browser failure is non-fatal — the parent will still navigate to
          // the result screen which polls the backend for status.
        }
      }
      onPaymentComplete(result);
    } catch {
      // Error handled by parent hook
    } finally {
      setPaying(false);
    }
  }, [canPay, selectedMethod, needsPhone, phoneNumber, sessionId, initiatePayment, onPaymentComplete]);

  // ── Loading state ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={[styles.center, { padding: spacing.xl }]}>
        <ActivityIndicator size="large" />
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: spacing.md }}>
          {t('wizard.payment.preparing')}
        </Text>
      </View>
    );
  }

  // ── Prepare error ──────────────────────────────────────────────────────
  if (prepareError || !prepareResult) {
    return (
      <View style={[styles.center, { padding: spacing.xl }]}>
        <MaterialCommunityIcons name="alert-circle" size={32} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: spacing.sm, textAlign: 'center' }}>
          {prepareError ?? t('wizard.payment.errorPrepare')}
        </Text>
      </View>
    );
  }

  const { tariff, errors, warnings, payment_methods } = prepareResult;

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.md, paddingBottom: spacing.xxl }}>
      {/* Validation errors */}
      {errors.length > 0 && (
        <View style={{ marginBottom: spacing.md }}>
          {errors.map((err) => (
            <ErrorWarningRow key={err.rule_id} item={err} type="error" colors={colors} spacing={spacing} borderRadius={borderRadius} />
          ))}
        </View>
      )}

      {/* Validation warnings */}
      {warnings.length > 0 && (
        <View style={{ marginBottom: spacing.md }}>
          {warnings.map((warn) => (
            <ErrorWarningRow key={warn.rule_id} item={warn} type="warning" colors={colors} spacing={spacing} borderRadius={borderRadius} />
          ))}
        </View>
      )}

      {/* Tariff breakdown */}
      <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: spacing.sm }}>
        {t('wizard.payment.tariffTitle')}
      </Text>
      <View style={{ marginBottom: spacing.sm }}>
        <View style={styles.tariffRow}>
          <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1 }}>
            {t('wizard.payment.baseAmount')}
          </Text>
          <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
            {formatCurrency(tariff.base_amount, tariff.currency)}
          </Text>
        </View>
        {tariff.supplements.map((sup, idx) => (
          <View key={`sup-${idx}`} style={styles.tariffRow}>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, flex: 1 }}>
              {sup.label_es ?? sup.code ?? t('wizard.payment.supplement')}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              + {formatCurrency(sup.amount, tariff.currency)}
            </Text>
          </View>
        ))}
        <Divider style={{ marginVertical: spacing.sm }} />
        <View style={styles.tariffRow}>
          <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '700', flex: 1 }}>
            {t('wizard.payment.total')}
          </Text>
          <Text variant="titleMedium" style={{ color: colors.primary, fontWeight: '700' }}>
            {formatCurrency(tariff.total_amount, tariff.currency)}
          </Text>
        </View>
      </View>

      <Divider style={{ marginVertical: spacing.md }} />

      {/* Payment method selection */}
      <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: spacing.sm }}>
        {t('wizard.payment.methodTitle')}
      </Text>
      <RadioButton.Group onValueChange={setSelectedMethod} value={selectedMethod}>
        {payment_methods.map((method) => (
          <View key={method.code} style={styles.methodRow}>
            <MaterialCommunityIcons
              name={(METHOD_ICONS[method.code] ?? 'cash') as keyof typeof MaterialCommunityIcons.glyphMap}
              size={22}
              color={selectedMethod === method.code ? colors.primary : colors.outline}
            />
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                {method.label_es}
              </Text>
            </View>
            <RadioButton value={method.code} />
          </View>
        ))}
      </RadioButton.Group>

      {/* Phone number input for mobile money */}
      {needsPhone && (
        <>
          <TextInput
            label={t('wizard.payment.phoneLabel')}
            placeholder="222XXXXXX"
            value={phoneNumber}
            onChangeText={setPhoneNumber}
            keyboardType="phone-pad"
            maxLength={9}
            mode="outlined"
            style={{ marginTop: spacing.md }}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={phoneNumber.length > 0 && !phoneValid}
            left={<TextInput.Affix text="+240" />}
          />
          {phoneNumber.length > 0 && !phoneValid && (
            <HelperText type="error" visible>
              {t('auth.invalidPhoneGE')}
            </HelperText>
          )}
        </>
      )}

      {/* Pay button */}
      <Button
        mode="contained"
        onPress={handlePay}
        loading={paying || isSaving}
        disabled={!canPay}
        style={{ marginTop: spacing.lg, borderRadius: borderRadius.sm }}
        contentStyle={{ paddingVertical: 4 }}
        icon="cash-check"
      >
        {t('wizard.payment.payButton', { amount: formatCurrency(tariff.total_amount, tariff.currency) })}
      </Button>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: Error / Warning row
// ---------------------------------------------------------------------------

function ErrorWarningRow({
  item,
  type,
  colors,
  spacing,
  borderRadius,
}: {
  item: ValidationError;
  type: 'error' | 'warning';
  colors: any;
  spacing: any;
  borderRadius: any;
}) {
  const bgColor = type === 'error' ? colors.errorContainer : `${colors.warning}20`;
  const iconColor = type === 'error' ? colors.error : colors.warning;
  const iconName = type === 'error' ? 'close-circle' : 'alert';

  return (
    <View
      style={[
        styles.validationRow,
        {
          backgroundColor: bgColor,
          padding: spacing.sm,
          borderRadius: borderRadius.sm,
          marginBottom: spacing.xs,
        },
      ]}
    >
      <MaterialCommunityIcons name={iconName} size={16} color={iconColor} />
      <Text variant="bodySmall" style={{ color: colors.onSurface, marginLeft: spacing.sm, flex: 1 }}>
        {item.message_es}
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  tariffRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  methodRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
  },
  validationRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
});
