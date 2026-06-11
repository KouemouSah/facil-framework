/**
 * Corporate tax calculator tab — 35% flat rate.
 */

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, TextInput, Button, Surface, Divider } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import { useTranslation } from 'react-i18next';

import { CORPORATE_TAX_RATE } from '../constants/calculator.constants';
import { formatCurrencyValue, parseNumberInput } from '../services/calculator-helpers';
import type { CorporateResult } from '../types/calculator.types';

import { ResultCard, BigStat } from './result-card';

interface CorporateTabProps {
  profit: string;
  onProfitChange: (v: string) => void;
  onReset: () => void;
  locale: string;
}

export function CorporateTab({ profit, onProfitChange, onReset, locale }: CorporateTabProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const formatCurrency = (v: number) => formatCurrencyValue(v, locale);

  const result = useMemo<CorporateResult | null>(() => {
    const p = parseNumberInput(profit);
    if (p <= 0) return null;
    const tax = (p * CORPORATE_TAX_RATE) / 100;
    return { profit: p, tax, netProfit: p - tax };
  }, [profit]);

  return (
    <View style={{ gap: spacing.md }}>
      <Surface
        elevation={1}
        style={[
          styles.card,
          {
            borderRadius: borderRadius.lg,
            backgroundColor: colors.surface,
            padding: spacing.md,
            gap: spacing.md,
          },
        ]}
      >
        <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
          {t('calculator.corporateTax')} ({CORPORATE_TAX_RATE}%)
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: -spacing.sm }}>
          {t('calculator.corporateTaxDesc')}
        </Text>

        <TextInput
          label={t('calculator.taxableProfit')}
          value={profit}
          onChangeText={onProfitChange}
          keyboardType="numeric"
          mode="outlined"
          placeholder="10000000"
          right={<TextInput.Affix text="XAF" />}
        />

        <Button mode="outlined" icon="refresh" onPress={onReset} compact style={styles.resetBtn}>
          {t('calculator.reset')}
        </Button>

        <Divider />

        <View
          style={{
            backgroundColor: colors.surfaceVariant,
            borderRadius: borderRadius.sm,
            padding: spacing.sm,
          }}
        >
          <Text
            variant="labelSmall"
            style={{ color: colors.onSurfaceVariant, fontWeight: '600', marginBottom: 2 }}
          >
            {t('calculator.formula')}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {t('calculator.corporateFormula')}
          </Text>
        </View>
      </Surface>

      <ResultCard
        title={t('calculator.result')}
        subtitle={t('calculator.corporateBreakdown')}
        hasResult={!!result}
        emptyIcon="office-building"
        emptyText={t('calculator.enterAmount')}
      >
        {result ? (
          <View style={{ gap: spacing.sm }}>
            <BigStat
              label={t('calculator.taxableProfit')}
              value={formatCurrency(result.profit)}
              background={colors.surfaceVariant}
              foreground={colors.onSurface}
            />
            <BigStat
              label={`${t('calculator.corporateTaxAmount')} (${CORPORATE_TAX_RATE}%)`}
              value={formatCurrency(result.tax)}
              background={colors.errorContainer}
              foreground={colors.error}
            />
            <BigStat
              label={t('calculator.netProfit')}
              value={formatCurrency(result.netProfit)}
              background={colors.secondaryContainer}
              foreground={colors.onSecondaryContainer}
            />
          </View>
        ) : null}
      </ResultCard>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {},
  resetBtn: {
    alignSelf: 'flex-start',
  },
});
