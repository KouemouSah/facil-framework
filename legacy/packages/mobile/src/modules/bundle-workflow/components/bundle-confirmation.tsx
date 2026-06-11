import { View, StyleSheet } from 'react-native';
import { Text, Button } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { useAppTheme } from '@core/theme';
import type { useBundleWizard } from '../services/bundle-hooks';

type Wizard = ReturnType<typeof useBundleWizard>;

function formatXAF(n: number): string {
  return n.toLocaleString('es-GQ', { maximumFractionDigits: 0 }) + ' XAF';
}

export function BundleConfirmationStep({ wizard, lang }: { wizard: Wizard; lang: string }) {
  const { colors } = useAppTheme();
  const router = useRouter();
  const result = wizard.paymentResult;

  if (!result) return null;

  const message = lang === 'fr' ? result.message_fr : lang === 'en' ? result.message_en : result.message_es;

  return (
    <View style={{ flex: 1, padding: 24, gap: 20, alignItems: 'center' }}>
      {/* Success icon */}
      <View style={[s.successCircle, { backgroundColor: '#E8F5E9' }]}>
        <MaterialCommunityIcons name="check-circle" size={56} color="#2E7D32" />
      </View>

      <Text variant="headlineSmall" style={{ fontWeight: '700', textAlign: 'center' }}>
        {lang === 'fr' ? 'Paiement initié' : lang === 'en' ? 'Payment initiated' : 'Pago iniciado'}
      </Text>

      {message && (
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, textAlign: 'center' }}>
          {message}
        </Text>
      )}

      {/* Payment details */}
      <View style={[s.detailCard, { backgroundColor: colors.surface, borderColor: colors.outlineVariant }]}>
        <View style={s.detailRow}>
          <Text variant="labelMedium" style={{ color: colors.outline }}>
            {lang === 'fr' ? 'Référence' : lang === 'en' ? 'Reference' : 'Referencia'}
          </Text>
          <Text variant="bodyMedium" style={{ fontWeight: '700', fontFamily: 'monospace' }}>
            {result.payment_reference}
          </Text>
        </View>
        {result.total_amount != null && (
          <View style={s.detailRow}>
            <Text variant="labelMedium" style={{ color: colors.outline }}>
              {lang === 'fr' ? 'Montant' : lang === 'en' ? 'Amount' : 'Monto'}
            </Text>
            <Text variant="bodyMedium" style={{ fontWeight: '700', color: colors.primary }}>
              {formatXAF(result.total_amount)}
            </Text>
          </View>
        )}
        <View style={s.detailRow}>
          <Text variant="labelMedium" style={{ color: colors.outline }}>
            {lang === 'fr' ? 'Obligations' : 'Obligations'}
          </Text>
          <Text variant="bodyMedium">{wizard.selectedObligationIds.size}</Text>
        </View>
      </View>

      {/* Next steps */}
      <View style={{ gap: 8, width: '100%' }}>
        <Text variant="titleSmall" style={{ fontWeight: '600' }}>
          {lang === 'fr' ? 'Prochaines étapes' : lang === 'en' ? 'Next steps' : 'Próximos pasos'}
        </Text>
        {[
          lang === 'fr' ? '1. Un agent validera votre paiement (1-3 jours)' : lang === 'en' ? '1. An agent will validate your payment (1-3 days)' : '1. Un agente validará su pago (1-3 días)',
          lang === 'fr' ? '2. Chaque entité traitera sa part' : lang === 'en' ? '2. Each entity will process its part' : '2. Cada entidad procesará su parte',
          lang === 'fr' ? '3. Recevez votre licence par email' : lang === 'en' ? '3. Receive your license by email' : '3. Recibirá su licencia por email',
        ].map((step, i) => (
          <Text key={i} variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>{step}</Text>
        ))}
      </View>

      {/* Actions */}
      <View style={{ gap: 10, width: '100%', marginTop: 8 }}>
        <Button mode="contained" onPress={() => router.push('/(tabs)/requests' as any)}>
          {lang === 'fr' ? 'Voir mes demandes' : lang === 'en' ? 'View my requests' : 'Ver mis solicitudes'}
        </Button>
        <Button mode="text" onPress={() => router.push('/(tabs)' as any)}>
          {lang === 'fr' ? 'Retour à l\'accueil' : lang === 'en' ? 'Back to home' : 'Volver al inicio'}
        </Button>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  successCircle: { width: 88, height: 88, borderRadius: 44, justifyContent: 'center', alignItems: 'center' },
  detailCard: { width: '100%', padding: 16, borderRadius: 12, borderWidth: 1, gap: 10 },
  detailRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
});
