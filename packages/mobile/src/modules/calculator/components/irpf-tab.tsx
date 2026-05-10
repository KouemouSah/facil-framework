/**
 * IRPF (income tax) calculator tab.
 *
 * Uses progressive brackets (0/10/15/20/25/35%). Calculates immediately
 * on input change — no submit button needed.
 */

import React, { useCallback, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, TextInput, Button, Surface, Divider } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import { useTranslation } from 'react-i18next';

import { IRPF_BRACKETS } from '../constants/calculator.constants';
import {
  formatCurrencyValue,
  formatPercent,
  parseNumberInput,
} from '../services/calculator-helpers';
import type { IrpfResult } from '../types/calculator.types';

import { ResultCard, KeyValueRow, BigStat } from './result-card';
import { TaxBracketsList } from './tax-brackets-list';

interface IrpfTabProps {
  amount: string;
  onAmountChange: (v: string) => void;
  onReset: () => void;
  locale: string;
}

const BRACKET_COLORS = ['#10B981', '#22C55E', '#84CC16', '#F59E0B', '#F97316', '#EF4444'];

export function IrpfTab({ amount, onAmountChange, onReset, locale }: IrpfTabProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const formatCurrency = useCallback((v: number) => formatCurrencyValue(v, locale), [locale]);

  const result = useMemo<IrpfResult | null>(() => {
    const gross = parseNumberInput(amount);
    if (gross <= 0) return null;

    let remaining = gross;
    let totalTax = 0;
    const breakdown: IrpfResult['breakdown'] = [];

    for (const bracket of IRPF_BRACKETS) {
      if (remaining <= 0) break;
      if (gross <= bracket.min) continue;

      const inBracket = Math.min(
        gross - bracket.min,
        bracket.max === Number.POSITIVE_INFINITY
          ? gross - bracket.min
          : bracket.max - bracket.min
      );

      const actual = Math.min(inBracket, remaining);
      if (actual > 0 && bracket.rate > 0) {
        const tax = (actual * bracket.rate) / 100;
        totalTax += tax;
        breakdown.push({
          bracket:
            bracket.max === Number.POSITIVE_INFINITY
              ? `> ${formatCurrency(bracket.min)}`
              : `${formatCurrency(bracket.min)} - ${formatCurrency(bracket.max)}`,
          taxable: actual,
          rate: bracket.rate,
          tax,
        });
        remaining -= actual;
      } else if (bracket.rate === 0) {
        remaining -= inBracket;
      }
    }

    return {
      grossAmount: gross,
      taxAmount: totalTax,
      netAmount: gross - totalTax,
      effectiveRate: (totalTax / gross) * 100,
      breakdown,
    };
  }, [amount, formatCurrency]);

  const bracketRows = useMemo(
    () =>
      IRPF_BRACKETS.map((b, idx) => ({
        range:
          b.max === Number.POSITIVE_INFINITY
            ? `> ${formatCurrency(b.min)}`
            : `${formatCurrency(b.min)} - ${formatCurrency(b.max)}`,
        rate: `${b.rate}%`,
        color: BRACKET_COLORS[idx] ?? colors.primary,
      })),
    [colors.primary, formatCurrency]
  );

  return (
    <View style={{ gap: spacing.md }}>
      {/* Input card */}
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
          {t('calculator.incomeTax')}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: -spacing.sm }}>
          {t('calculator.incomeTaxDesc')}
        </Text>

        <TextInput
          label={t('calculator.annualIncome')}
          value={amount}
          onChangeText={onAmountChange}
          keyboardType="numeric"
          mode="outlined"
          placeholder="5000000"
          right={<TextInput.Affix text="XAF" />}
        />

        <Button
          mode="outlined"
          icon="refresh"
          onPress={onReset}
          compact
          style={styles.resetBtn}
        >
          {t('calculator.reset')}
        </Button>

        <Divider />

        <TaxBracketsList brackets={bracketRows} title={t('calculator.taxBrackets')} />
      </Surface>

      {/* Result card */}
      <ResultCard
        title={t('calculator.result')}
        subtitle={t('calculator.calculationBreakdown')}
        hasResult={!!result}
        emptyIcon="calculator-variant-outline"
        emptyText={t('calculator.enterAmount')}
      >
        {result ? (
          <View style={{ gap: spacing.md }}>
            <View style={styles.statsGrid}>
              <BigStat
                label={t('calculator.grossIncome')}
                value={formatCurrency(result.grossAmount)}
                background={colors.surfaceVariant}
                foreground={colors.onSurface}
              />
              <BigStat
                label={t('calculator.totalTax')}
                value={formatCurrency(result.taxAmount)}
                background={colors.errorContainer}
                foreground={colors.error}
              />
              <BigStat
                label={t('calculator.netIncome')}
                value={formatCurrency(result.netAmount)}
                background={colors.secondaryContainer}
                foreground={colors.onSecondaryContainer}
              />
              <BigStat
                label={t('calculator.effectiveRate')}
                value={formatPercent(result.effectiveRate, locale)}
                background={colors.primaryContainer}
                foreground={colors.onPrimaryContainer}
              />
            </View>

            <Divider />

            <Text variant="labelMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
              {t('calculator.breakdownByBracket')}
            </Text>
            <View style={{ gap: spacing.xs }}>
              {result.breakdown.map((item, idx) => (
                <KeyValueRow
                  key={idx}
                  label={`${item.bracket}  @ ${item.rate}%`}
                  value={formatCurrency(item.tax)}
                />
              ))}
            </View>
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
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
});
