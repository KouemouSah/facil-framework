/**
 * VAT calculator tab — 15% standard rate, mode toggle (add / extract).
 */

import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, TextInput, Button, Surface, Divider, SegmentedButtons } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import { useTranslation } from 'react-i18next';

import { VAT_STANDARD_RATE } from '../constants/calculator.constants';
import { formatCurrencyValue, parseNumberInput } from '../services/calculator-helpers';
import type { VatMode, VatResult } from '../types/calculator.types';

import { ResultCard, BigStat } from './result-card';

interface VatTabProps {
  amount: string;
  onAmountChange: (v: string) => void;
  mode: VatMode;
  onModeChange: (m: VatMode) => void;
  onReset: () => void;
  locale: string;
}

export function VatTab({ amount, onAmountChange, mode, onModeChange, onReset, locale }: VatTabProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const formatCurrency = (v: number) => formatCurrencyValue(v, locale);

  const result = useMemo<VatResult | null>(() => {
    const value = parseNumberInput(amount);
    if (value <= 0) return null;
    if (mode === 'add') {
      const vat = (value * VAT_STANDARD_RATE) / 100;
      return { baseAmount: value, vatAmount: vat, totalAmount: value + vat };
    }
    const baseAmount = value / (1 + VAT_STANDARD_RATE / 100);
    return { baseAmount, vatAmount: value - baseAmount, totalAmount: value };
  }, [amount, mode]);

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
          {t('calculator.vat')} ({VAT_STANDARD_RATE}%)
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: -spacing.sm }}>
          {t('calculator.vatDesc')}
        </Text>

        <View>
          <Text
            variant="labelMedium"
            style={{ color: colors.onSurfaceVariant, marginBottom: spacing.xs }}
          >
            {t('calculator.calculationType')}
          </Text>
          <SegmentedButtons
            value={mode}
            onValueChange={(v) => onModeChange(v as VatMode)}
            buttons={[
              { value: 'add', label: t('calculator.addVat') },
              { value: 'extract', label: t('calculator.extractVat') },
            ]}
          />
        </View>

        <TextInput
          label={mode === 'add' ? t('calculator.baseAmount') : t('calculator.totalWithVat')}
          value={amount}
          onChangeText={onAmountChange}
          keyboardType="numeric"
          mode="outlined"
          placeholder="1000000"
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
            {mode === 'add' ? t('calculator.vatAddFormula') : t('calculator.vatExtractFormula')}
          </Text>
        </View>
      </Surface>

      <ResultCard
        title={t('calculator.result')}
        subtitle={t('calculator.vatBreakdown')}
        hasResult={!!result}
        emptyIcon="receipt"
        emptyText={t('calculator.enterAmount')}
      >
        {result ? (
          <View style={{ gap: spacing.sm }}>
            <BigStat
              label={t('calculator.baseAmount')}
              value={formatCurrency(result.baseAmount)}
              background={colors.surfaceVariant}
              foreground={colors.onSurface}
            />
            <BigStat
              label={`${t('calculator.vatAmount')} (${VAT_STANDARD_RATE}%)`}
              value={formatCurrency(result.vatAmount)}
              background={colors.tertiaryContainer}
              foreground={colors.onTertiaryContainer}
            />
            <BigStat
              label={t('calculator.totalWithVat')}
              value={formatCurrency(result.totalAmount)}
              background={colors.primaryContainer}
              foreground={colors.onPrimaryContainer}
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
