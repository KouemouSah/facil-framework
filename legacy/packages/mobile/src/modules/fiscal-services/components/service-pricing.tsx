/**
 * ServicePricing — Native Android pricing display
 *
 * Flat layout: expedition price + renewal price + method + processing time.
 * Currency (XAF) is part of formatCurrency(), not a separate badge.
 */

import { StyleSheet, View } from 'react-native';
import { Text, Divider } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import type { PricingInfo } from '../types/services.types';

const METHOD_LABELS: Record<string, string> = {
  fixed_expedition: 'Tasa fija',
  fixed_renewal: 'Tasa fija (renovación)',
  percentage_based: 'Porcentaje',
  unit_based: 'Por unidad',
  tiered_rates: 'Escalonado',
  formula_based: 'Fórmula',
  fixed_plus_unit: 'Fija + por unidad',
};

interface ServicePricingProps {
  pricing: PricingInfo;
  processing_time_days?: number;
}

export function ServicePricing({ pricing, processing_time_days }: ServicePricingProps) {
  const { colors } = useAppTheme();
  const { t } = useTranslation();

  const isFree = pricing.expedition_price === 0 && pricing.renewal_price === 0;
  const hasRenewal = pricing.renewal_price > 0 && pricing.renewal_price !== pricing.expedition_price;
  const methodLabel = METHOD_LABELS[pricing.calculation_method] ?? pricing.calculation_method;

  return (
    <View>
      <View style={styles.header}>
        <MaterialCommunityIcons name="cash-multiple" size={18} color={colors.primary} />
        <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginLeft: 6 }}>
          {t('services.tariff')}
        </Text>
      </View>

      {isFree ? (
        <View style={styles.freeRow}>
          <MaterialCommunityIcons name="gift-outline" size={20} color={colors.primary} />
          <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 16, marginLeft: 8 }}>
            {t('services.freeService')}
          </Text>
        </View>
      ) : (
        <>
          {/* Expedition */}
          <View style={styles.priceRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('services.expedition')}
            </Text>
            <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 18 }}>
              {formatCurrency(pricing.expedition_price)}
            </Text>
          </View>

          {/* Renewal */}
          {hasRenewal && (
            <View style={styles.priceRow}>
              <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
                {t('services.renewal')}
              </Text>
              <Text style={{ color: colors.onSurface, fontWeight: '600', fontSize: 15 }}>
                {formatCurrency(pricing.renewal_price)}
              </Text>
            </View>
          )}

          {/* Percentage */}
          {pricing.percentage_rate != null && pricing.percentage_rate > 0 && (
            <View style={styles.priceRow}>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {t('services.tariff')}
              </Text>
              <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
                {pricing.percentage_rate}%
              </Text>
            </View>
          )}
        </>
      )}

      {/* Meta: method + processing time (inline) */}
      <Divider style={{ marginVertical: 8 }} />
      <View style={styles.metaRow}>
        <MaterialCommunityIcons name="calculator-variant" size={14} color={colors.outline} />
        <Text variant="labelSmall" style={{ color: colors.outline, marginLeft: 4 }}>{methodLabel}</Text>
        {processing_time_days != null && processing_time_days > 0 && (
          <>
            <Text variant="labelSmall" style={{ color: colors.outline, marginHorizontal: 8 }}>|</Text>
            <MaterialCommunityIcons name="clock-outline" size={14} color={colors.outline} />
            <Text variant="labelSmall" style={{ color: colors.outline, marginLeft: 4 }}>
              {t('services.processingDays', { count: processing_time_days })}
            </Text>
          </>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  freeRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  priceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', paddingVertical: 4 },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
});
