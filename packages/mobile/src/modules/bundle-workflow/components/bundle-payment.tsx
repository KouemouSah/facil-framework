import { View, StyleSheet } from 'react-native';
import { Text, TextInput, RadioButton, ActivityIndicator } from 'react-native-paper';
import { useAppTheme } from '@core/theme';
import { CompanyCard } from './company-card';
import type { useBundleWizard } from '../services/bundle-hooks';
import type { PaymentMethod } from '../types';

type Wizard = ReturnType<typeof useBundleWizard>;

function formatXAF(n: number): string {
  return n.toLocaleString('es-GQ', { maximumFractionDigits: 0 }) + ' XAF';
}

export function BundlePaymentStep({ wizard, lang }: { wizard: Wizard; lang: string }) {
  const { colors } = useAppTheme();
  const selectedTotal = wizard.licenseData?.obligations
    .filter((o) => wizard.selectedObligationIds.has(o.id))
    .reduce((sum, o) => sum + o.total, 0) ?? 0;

  if (wizard.isPaymentProcessing) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 }}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline }}>
          {lang === 'fr' ? 'Traitement du paiement...' : lang === 'en' ? 'Processing payment...' : 'Procesando pago...'}
        </Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, padding: 16, gap: 16 }}>
      {wizard.selectedCompany && <CompanyCard company={wizard.selectedCompany} />}

      {/* Summary */}
      <View style={[s.summaryCard, { backgroundColor: colors.surfaceVariant }]}>
        <Text variant="titleSmall" style={{ fontWeight: '600' }}>
          {lang === 'fr' ? 'Résumé' : lang === 'en' ? 'Summary' : 'Resumen'}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.outline, marginTop: 4 }}>
          {wizard.selectedObligationIds.size} {lang === 'fr' ? 'obligations' : 'obligations'} · {wizard.selectedMode}
        </Text>
        <Text variant="headlineSmall" style={{ fontWeight: '800', color: colors.primary, marginTop: 8 }}>
          {formatXAF(selectedTotal)}
        </Text>
      </View>

      {/* Payment method */}
      <Text variant="titleSmall" style={{ fontWeight: '600' }}>
        {lang === 'fr' ? 'Méthode de paiement' : lang === 'en' ? 'Payment method' : 'Método de pago'}
      </Text>

      <RadioButton.Group
        onValueChange={(v) => wizard.setPaymentMethod(v as PaymentMethod)}
        value={wizard.paymentMethod || ''}
      >
        <RadioButton.Item
          label={lang === 'fr' ? 'Mobile Money (BANGE)' : 'Mobile Money (BANGE)'}
          value="mobile_money"
          style={s.radioItem}
        />
        <RadioButton.Item
          label={lang === 'fr' ? 'Espèces (Agence Trésor)' : lang === 'en' ? 'Cash (Treasury Agency)' : 'Efectivo (Agencia Tesoro)'}
          value="cash"
          style={s.radioItem}
        />
      </RadioButton.Group>

      {/* Phone input for mobile_money */}
      {wizard.paymentMethod === 'mobile_money' && (
        <TextInput
          label={lang === 'fr' ? 'Numéro de téléphone' : lang === 'en' ? 'Phone number' : 'Número de teléfono'}
          value={wizard.phoneNumber}
          onChangeText={wizard.setPhoneNumber}
          mode="outlined"
          keyboardType="phone-pad"
          placeholder="+240 222 XXX XXX"
          maxLength={12}
          left={<TextInput.Icon icon="phone" />}
        />
      )}

      {/* Error */}
      {wizard.error && (
        <Text variant="bodySmall" style={{ color: colors.error }}>{wizard.error}</Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  summaryCard: { padding: 16, borderRadius: 12 },
  radioItem: { paddingVertical: 4 },
});
