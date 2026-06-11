/**
 * Fiscal services calculator tab — picker + dynamic form (percentage or formula).
 *
 * Calculation runs on `Calculate` button press (mirroring the web's
 * `calculationTriggered` flag). Reset wipes inputs and the trigger.
 */

import React, { useMemo, useState, useCallback } from 'react';
import { StyleSheet, View, Pressable } from 'react-native';
import {
  Text,
  TextInput,
  Button,
  Surface,
  Divider,
  Menu,
  IconButton,
} from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useTranslation } from 'react-i18next';

import {
  evaluateFormula,
  formatCurrencyValue,
  parseNumberInput,
} from '../services/calculator-helpers';
import type {
  CalculableService,
  FormulaService,
  FormulaVariable,
  PercentageService,
  ServiceCalculationResult,
} from '../types/calculator.types';

import { ResultCard, KeyValueRow, BigStat } from './result-card';

interface ServicesTabProps {
  services: CalculableService[];
  locale: string;
}

function getLocalized(value: { es: string; fr: string; en: string }, locale: string): string {
  if (locale.startsWith('fr')) return value.fr;
  if (locale.startsWith('en')) return value.en;
  return value.es;
}

export function ServicesTab({ services, locale }: ServicesTabProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [triggered, setTriggered] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const selectedService = useMemo(
    () => services.find((s) => s.id === selectedId) ?? null,
    [services, selectedId]
  );

  const formatCurrency = useCallback(
    (v: number) => formatCurrencyValue(v, locale),
    [locale]
  );

  const getServiceName = useCallback(
    (s: CalculableService): string =>
      getLocalized({ es: s.name_es, fr: s.name_fr, en: s.name_en }, locale),
    [locale]
  );

  const getVariableLabel = useCallback(
    (v: FormulaVariable): string =>
      getLocalized({ es: v.label_es, fr: v.label_fr, en: v.label_en }, locale),
    [locale]
  );

  const getVariableDescription = useCallback(
    (v: FormulaVariable): string | undefined => {
      const value = getLocalized(
        { es: v.description_es ?? '', fr: v.description_fr ?? '', en: v.description_en ?? '' },
        locale
      );
      return value || undefined;
    },
    [locale]
  );

  const getFormulaDescription = useCallback(
    (s: FormulaService): string =>
      getLocalized(
        {
          es: s.formula_description_es,
          fr: s.formula_description_fr,
          en: s.formula_description_en,
        },
        locale
      ),
    [locale]
  );

  const result = useMemo<ServiceCalculationResult | null>(() => {
    if (!selectedService || !triggered) return null;

    if (selectedService.type === 'percentage') {
      const base = parseNumberInput(inputs['baseAmount'] ?? '0');
      if (base <= 0) return null;
      const value = (base * selectedService.percentage) / 100;
      return {
        serviceName: getServiceName(selectedService),
        result: value,
        formula: `${selectedService.percentage}% × ${formatCurrency(base)}`,
        breakdown: [
          { label: t('calculator.baseAmount'), value: formatCurrency(base) },
          { label: t('calculator.percentageRate'), value: `${selectedService.percentage}%` },
        ],
      };
    }

    if (selectedService.type === 'formula') {
      const variables: Record<string, number> = {};
      const breakdown: { label: string; value: string }[] = [];

      for (const v of selectedService.variables) {
        const raw = inputs[v.key];
        const num = parseNumberInput(raw ?? String(v.defaultValue ?? 0));
        variables[v.key] = num;
        breakdown.push({
          label: getVariableLabel(v),
          value: v.type === 'currency' ? formatCurrency(num) : String(num),
        });
      }

      const value = evaluateFormula(selectedService.formula, variables);
      if (value === null) return null;

      return {
        serviceName: getServiceName(selectedService),
        result: value,
        formula: getFormulaDescription(selectedService),
        breakdown,
      };
    }

    return null;
  }, [
    selectedService,
    inputs,
    triggered,
    getServiceName,
    getVariableLabel,
    getFormulaDescription,
    formatCurrency,
    t,
  ]);

  const handleSelect = (id: number) => {
    setSelectedId(id);
    setInputs({});
    setTriggered(false);
    setPickerOpen(false);
  };

  const handleInput = (key: string, value: string) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
    setTriggered(false);
  };

  const handleCalculate = () => {
    setTriggered(true);
  };

  const handleReset = () => {
    setSelectedId(null);
    setInputs({});
    setTriggered(false);
  };

  const renderPercentageForm = (service: PercentageService) => (
    <View style={{ gap: spacing.sm }}>
      <TextInput
        label={t('calculator.baseAmountForPercentage')}
        value={inputs['baseAmount'] ?? ''}
        onChangeText={(v) => handleInput('baseAmount', v)}
        keyboardType="numeric"
        mode="outlined"
        placeholder="1000000"
        right={<TextInput.Affix text="XAF" />}
      />
      <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
        {t('calculator.percentageRate')}: {service.percentage}%
      </Text>
    </View>
  );

  const renderFormulaForm = (service: FormulaService) => (
    <View style={{ gap: spacing.sm }}>
      {service.variables.map((v) => {
        const desc = getVariableDescription(v);
        return (
          <View key={v.key} style={{ gap: 4 }}>
            <TextInput
              label={getVariableLabel(v)}
              value={inputs[v.key] ?? ''}
              onChangeText={(val) => handleInput(v.key, val)}
              keyboardType="numeric"
              mode="outlined"
              placeholder={v.defaultValue?.toString() ?? '0'}
              right={v.type === 'currency' ? <TextInput.Affix text="XAF" /> : undefined}
            />
            {desc ? (
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {desc}
              </Text>
            ) : null}
          </View>
        );
      })}
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
          {getFormulaDescription(service)}
        </Text>
      </View>
    </View>
  );

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
          {t('calculator.fiscalServices')}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: -spacing.sm }}>
          {t('calculator.fiscalServicesDesc')}
        </Text>

        {/* Service picker */}
        <View>
          <Text
            variant="labelMedium"
            style={{ color: colors.onSurfaceVariant, marginBottom: spacing.xs }}
          >
            {t('calculator.selectService')}
          </Text>
          <Menu
            visible={pickerOpen}
            onDismiss={() => setPickerOpen(false)}
            anchor={
              <Pressable onPress={() => setPickerOpen(true)}>
                <View
                  pointerEvents="none"
                  // Visual trigger: a TextInput-like field that opens the menu on tap
                >
                  <TextInput
                    mode="outlined"
                    value={selectedService ? getServiceName(selectedService) : ''}
                    placeholder={t('calculator.selectServicePlaceholder')}
                    editable={false}
                    right={<TextInput.Icon icon="chevron-down" />}
                  />
                </View>
              </Pressable>
            }
          >
            {services.map((s) => (
              <Menu.Item
                key={s.id}
                onPress={() => handleSelect(s.id)}
                title={getServiceName(s)}
              />
            ))}
          </Menu>
          <Text
            variant="bodySmall"
            style={{ color: colors.onSurfaceVariant, marginTop: spacing.xs }}
          >
            {t('calculator.servicesCount', { count: services.length })}
          </Text>
        </View>

        {selectedService ? (
          <>
            <Divider />

            {selectedService.type === 'percentage'
              ? renderPercentageForm(selectedService)
              : renderFormulaForm(selectedService)}

            <View style={styles.actionRow}>
              <Button
                mode="contained"
                icon="calculator"
                onPress={handleCalculate}
                style={styles.calcBtn}
              >
                {t('calculator.calculate')}
              </Button>
              <IconButton
                icon="refresh"
                mode="outlined"
                onPress={handleReset}
                accessibilityLabel={t('calculator.reset')}
              />
            </View>
          </>
        ) : (
          <View style={[styles.empty, { paddingVertical: spacing.xl }]}>
            <MaterialCommunityIcons
              name="file-document-outline"
              size={48}
              color={colors.outlineVariant}
            />
            <Text
              variant="bodyMedium"
              style={{
                color: colors.onSurfaceVariant,
                marginTop: spacing.sm,
                textAlign: 'center',
              }}
            >
              {t('calculator.selectServicePrompt')}
            </Text>
          </View>
        )}
      </Surface>

      <ResultCard
        title={t('calculator.result')}
        subtitle={result ? result.serviceName : t('calculator.serviceCalculationResult')}
        hasResult={!!result}
        emptyIcon="calculator-variant-outline"
        emptyText={
          selectedService ? t('calculator.enterVariables') : t('calculator.selectServiceFirst')
        }
      >
        {result ? (
          <View style={{ gap: spacing.md }}>
            <BigStat
              label={t('calculator.calculatedAmount')}
              value={formatCurrency(result.result)}
              background={colors.primaryContainer}
              foreground={colors.onPrimaryContainer}
            />

            <Divider />

            <View style={{ gap: spacing.xs }}>
              <Text variant="labelMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
                {t('calculator.calculationBreakdown')}
              </Text>
              <KeyValueRow label={t('calculator.formula')} value={result.formula} />
              {result.breakdown.map((item, idx) => (
                <KeyValueRow key={idx} label={item.label} value={item.value} />
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
  actionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  calcBtn: {
    flex: 1,
  },
  empty: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
