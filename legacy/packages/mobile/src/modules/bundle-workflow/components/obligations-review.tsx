import { View, StyleSheet, FlatList, Pressable } from 'react-native';
import { Text, Button, Divider, ActivityIndicator, SegmentedButtons, Checkbox } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useAppTheme } from '@core/theme';
import { CompanyCard } from './company-card';
import type { useBundleWizard } from '../services/bundle-hooks';
import type { ProcessingMode } from '../types';

type Wizard = ReturnType<typeof useBundleWizard>;

const FEE_COLORS: Record<string, string> = { tesoro: '#1565C0', municipal: '#2E7D32', chamber: '#6A1B9A' };

function formatXAF(n: number): string {
  return n.toLocaleString('es-GQ', { maximumFractionDigits: 0 }) + ' XAF';
}

export function ObligationsReviewStep({ wizard, lang }: { wizard: Wizard; lang: string }) {
  const { colors } = useAppTheme();

  if (wizard.isInitiating) {
    return <ActivityIndicator size="large" style={{ flex: 1, justifyContent: 'center' }} color={colors.primary} />;
  }

  if (!wizard.licenseData) {
    return (
      <View style={{ padding: 24, alignItems: 'center', gap: 12 }}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.outline} />
        <Text variant="bodyMedium" style={{ color: colors.outline }}>
          {lang === 'fr' ? 'Aucune obligation chargée' : lang === 'en' ? 'No obligations loaded' : 'No hay obligaciones cargadas'}
        </Text>
      </View>
    );
  }

  const { obligations } = wizard.licenseData;
  const isPerLine = wizard.selectedMode === 'per_line';
  const selectedTotal = obligations
    .filter((o) => wizard.selectedObligationIds.has(o.id))
    .reduce((sum, o) => sum + o.total, 0);

  return (
    <View style={{ flex: 1 }}>
      {/* Company summary */}
      {wizard.selectedCompany && (
        <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
          <CompanyCard company={wizard.selectedCompany} />
        </View>
      )}

      {/* Mode switcher */}
      <View style={{ paddingHorizontal: 16, paddingVertical: 12 }}>
        <SegmentedButtons
          value={wizard.selectedMode}
          onValueChange={(v) => {
            wizard.setSelectedMode(v as ProcessingMode);
            if (v === 'consolidated') wizard.selectAllObligations();
          }}
          buttons={[
            { value: 'per_line', label: lang === 'fr' ? 'Par ligne' : lang === 'en' ? 'Per line' : 'Por línea' },
            { value: 'consolidated', label: lang === 'fr' ? 'Consolidé' : lang === 'en' ? 'Consolidated' : 'Consolidado' },
          ]}
          density="small"
        />
      </View>

      {/* Select/Deselect all (per_line only) */}
      {isPerLine && (
        <View style={{ flexDirection: 'row', paddingHorizontal: 16, gap: 8, paddingBottom: 8 }}>
          <Button mode="text" compact onPress={wizard.selectAllObligations}>
            {lang === 'fr' ? 'Tout sélectionner' : lang === 'en' ? 'Select all' : 'Seleccionar todo'}
          </Button>
          <Button mode="text" compact onPress={wizard.deselectAllObligations}>
            {lang === 'fr' ? 'Tout désélectionner' : lang === 'en' ? 'Deselect all' : 'Deseleccionar todo'}
          </Button>
        </View>
      )}

      {/* Obligations list */}
      <FlatList
        data={obligations}
        keyExtractor={(item) => item.id}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: isPerLine ? 48 : 16 }} />}
        contentContainerStyle={{ paddingBottom: 100 }}
        renderItem={({ item }) => {
          const isPaid = item.status === 'paid';
          const isSelected = wizard.selectedObligationIds.has(item.id);
          const feeColor = FEE_COLORS[item.fee_type] || colors.primary;
          return (
            <Pressable
              style={[s.row, isPaid && { opacity: 0.4 }]}
              onPress={() => !isPaid && item.is_payable && isPerLine && wizard.toggleObligation(item.id)}
              disabled={isPaid || !item.is_payable || !isPerLine}
            >
              {isPerLine && (
                <Checkbox
                  status={isSelected ? 'checked' : 'unchecked'}
                  onPress={() => wizard.toggleObligation(item.id)}
                  disabled={isPaid || !item.is_payable}
                />
              )}
              <View style={{ flex: 1 }}>
                <Text variant="bodySmall" style={{ fontWeight: '500' }} numberOfLines={2}>
                  {item.fiscal_service_name}
                </Text>
                <View style={{ flexDirection: 'row', gap: 6, marginTop: 2 }}>
                  <View style={[s.feeBadge, { backgroundColor: feeColor + '20' }]}>
                    <Text style={{ fontSize: 10, color: feeColor, fontWeight: '600' }}>{item.fee_type}</Text>
                  </View>
                  {isPaid && (
                    <View style={[s.feeBadge, { backgroundColor: '#E8F5E9' }]}>
                      <Text style={{ fontSize: 10, color: '#2E7D32', fontWeight: '600' }}>
                        {lang === 'fr' ? 'Payé' : lang === 'en' ? 'Paid' : 'Pagado'}
                      </Text>
                    </View>
                  )}
                </View>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text variant="bodySmall" style={{ fontWeight: '700' }}>{formatXAF(item.amount)}</Text>
                {item.penalty_amount ? (
                  <Text variant="labelSmall" style={{ color: colors.error }}>+{formatXAF(item.penalty_amount)}</Text>
                ) : null}
              </View>
            </Pressable>
          );
        }}
      />

      {/* Total bar */}
      <View style={[s.totalBar, { backgroundColor: colors.primary }]}>
        <Text style={{ color: colors.onPrimary, fontWeight: '600' }}>
          {lang === 'fr' ? 'Total sélectionné' : lang === 'en' ? 'Selected total' : 'Total seleccionado'}
        </Text>
        <Text style={{ color: colors.onPrimary, fontWeight: '800', fontSize: 18 }}>{formatXAF(selectedTotal)}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10 },
  feeBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4 },
  totalBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14 },
});
