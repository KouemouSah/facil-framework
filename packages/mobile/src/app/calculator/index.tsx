/**
 * Calculator Screen — full port of the web `calculateur` page.
 *
 * 4 tabs: IRPF, VAT, Corporate, Fiscal Services.
 * All calculations run client-side. Service overrides come from
 * `GET /api/v1/homepage/calculator/config` with graceful fallback to
 * `DEFAULT_CALCULABLE_SERVICES` when the endpoint is unavailable.
 */

import React, { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, SegmentedButtons, Surface, Text } from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

import {
  CorporateTab,
  IrpfTab,
  ServicesTab,
  VatTab,
  useMergedCalculableServices,
  type CalculatorLanguage,
  type CalculatorTab,
  type VatMode,
} from '@modules/calculator';

function resolveLanguage(i18nLanguage: string | undefined): CalculatorLanguage {
  const lang = (i18nLanguage ?? 'es').slice(0, 2).toLowerCase();
  if (lang === 'fr' || lang === 'en') return lang;
  return 'es';
}

export default function CalculatorScreen() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const insets = useSafeAreaInsets();

  const language = resolveLanguage(i18n.language);
  const services = useMergedCalculableServices(language);

  const [activeTab, setActiveTab] = useState<CalculatorTab>('irpf');
  const [irpfAmount, setIrpfAmount] = useState('');
  const [vatAmount, setVatAmount] = useState('');
  const [vatMode, setVatMode] = useState<VatMode>('add');
  const [corporateProfit, setCorporateProfit] = useState('');

  const handleResetIrpf = () => setIrpfAmount('');
  const handleResetVat = () => {
    setVatAmount('');
    setVatMode('add');
  };
  const handleResetCorporate = () => setCorporateProfit('');

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View
        style={[
          styles.header,
          {
            paddingHorizontal: spacing.sm,
            paddingVertical: spacing.sm,
            backgroundColor: colors.surface,
            borderBottomColor: colors.outlineVariant,
          },
        ]}
      >
        <Button mode="text" icon="arrow-left" onPress={() => router.back()} compact>
          {t('common.back')}
        </Button>
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
          {t('calculator.title')}
        </Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { padding: spacing.md, gap: spacing.md, paddingBottom: spacing.xxl + insets.bottom },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        {/* Page intro */}
        <View>
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
            {t('calculator.description')}
          </Text>
        </View>

        {/* Tabs */}
        <SegmentedButtons
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as CalculatorTab)}
          density="medium"
          buttons={[
            {
              value: 'irpf',
              label: 'IRPF',
              icon: 'calculator',
            },
            {
              value: 'vat',
              label: t('calculator.vat'),
              icon: 'receipt',
            },
            {
              value: 'corporate',
              label: 'IS',
              icon: 'office-building',
            },
            {
              value: 'services',
              label: t('calculator.services'),
              icon: 'file-document-outline',
            },
          ]}
        />

        {/* Tab content */}
        {activeTab === 'irpf' ? (
          <IrpfTab
            amount={irpfAmount}
            onAmountChange={setIrpfAmount}
            onReset={handleResetIrpf}
            locale={language}
          />
        ) : null}
        {activeTab === 'vat' ? (
          <VatTab
            amount={vatAmount}
            onAmountChange={setVatAmount}
            mode={vatMode}
            onModeChange={setVatMode}
            onReset={handleResetVat}
            locale={language}
          />
        ) : null}
        {activeTab === 'corporate' ? (
          <CorporateTab
            profit={corporateProfit}
            onProfitChange={setCorporateProfit}
            onReset={handleResetCorporate}
            locale={language}
          />
        ) : null}
        {activeTab === 'services' ? (
          <ServicesTab services={services} locale={language} />
        ) : null}

        {/* Disclaimer */}
        <Surface
          elevation={0}
          style={[
            styles.disclaimer,
            {
              backgroundColor: `${colors.warning}1A`,
              borderColor: `${colors.warning}66`,
              borderRadius: borderRadius.md,
              padding: spacing.md,
            },
          ]}
        >
          <MaterialCommunityIcons
            name="alert-circle-outline"
            size={20}
            color={colors.warning}
            style={{ marginRight: spacing.sm }}
          />
          <Text
            variant="bodySmall"
            style={{ color: colors.warning, flex: 1 }}
          >
            {t('calculator.disclaimer')}
          </Text>
        </Surface>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  headerSpacer: {
    width: 64,
  },
  scrollContent: {
    flexGrow: 1,
  },
  disclaimer: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    borderWidth: 1,
  },
});
