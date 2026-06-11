/**
 * Guide Tab — Practical guide for citizens
 *
 * 3 sections via SegmentedButtons:
 * - Pasos: 8-step workflow (account → login → select → upload → form → rdv → pay → confirm)
 * - FAQ: Common questions (accordion)
 * - Formularios: 14 downloadable PDF forms with preview via browser
 */

import { useState } from 'react';
import { StyleSheet, View, ScrollView, Linking, Alert } from 'react-native';
import { Text, SegmentedButtons, List, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

type Section = 'steps' | 'faq' | 'forms';

// ---------------------------------------------------------------------------
// Workflow Steps (8 steps: account creation through confirmation)
// ---------------------------------------------------------------------------

const STEPS = [
  { icon: 'account-plus-outline' as const, color: '#0277BD' },
  { icon: 'login' as const, color: '#00838F' },
  { icon: 'clipboard-list-outline' as const, color: '#2E7D32' },
  { icon: 'file-upload-outline' as const, color: '#1565C0' },
  { icon: 'form-select' as const, color: '#E65100' },
  { icon: 'calendar-check' as const, color: '#7B1FA2' },
  { icon: 'credit-card-outline' as const, color: '#C62828' },
  { icon: 'check-circle-outline' as const, color: '#00695C' },
];

function StepsSection({ t, colors }: { t: any; colors: any }) {
  return (
    <View style={{ gap: 4 }}>
      <View style={{ paddingHorizontal: 16, paddingVertical: 12, backgroundColor: colors.primaryContainer, marginHorizontal: 16, borderRadius: 12, marginBottom: 8 }}>
        <Text variant="bodyMedium" style={{ color: colors.onPrimaryContainer, lineHeight: 22 }}>
          {t('guide.steps.intro')}
        </Text>
      </View>

      {STEPS.map((step, i) => (
        <View key={i}>
          <List.Item
            title={t(`guide.steps.${i + 1}_title`)}
            description={t(`guide.steps.${i + 1}_desc`)}
            descriptionNumberOfLines={3}
            left={() => (
              <View style={[styles.stepCircle, { backgroundColor: step.color + '18' }]}>
                <MaterialCommunityIcons name={step.icon} size={24} color={step.color} />
              </View>
            )}
          />
          {i < STEPS.length - 1 && <Divider style={{ marginLeft: 72 }} />}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// FAQ Section
// ---------------------------------------------------------------------------

const FAQ_COUNT = 6;

function FaqSection({ t, colors }: { t: any; colors: any }) {
  return (
    <View>
      {Array.from({ length: FAQ_COUNT }, (_, i) => (
        <List.Accordion
          key={i}
          title={t(`guide.faq.q${i + 1}`)}
          titleNumberOfLines={3}
          titleStyle={{ fontSize: 14, fontWeight: '500' }}
          left={(props) => <List.Icon {...props} icon="help-circle-outline" color={colors.primary} />}
          style={{ backgroundColor: colors.surface }}
        >
          <View style={{ paddingHorizontal: 16, paddingBottom: 16, paddingLeft: 56 }}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, lineHeight: 22 }}>
              {t(`guide.faq.a${i + 1}`)}
            </Text>
          </View>
        </List.Accordion>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Forms Section — 14 real PDF forms from web
// ---------------------------------------------------------------------------

const BASE_FORMS_URL = 'https://taxasge.emacsah.com/documents/formulaires';

const FORMS = [
  { key: 'retencion_3_petrolero', file: '3_RESIDENTES_PETROLERO.pdf', icon: 'file-percent-outline' as const },
  { key: 'retencion_5_petrolero', file: '5_RESIDENTES_PETROLERO.pdf', icon: 'file-percent-outline' as const },
  { key: 'retencion_10_nr_petrolero', file: '10_NO-RESIDENTES_PETROLERO.pdf', icon: 'file-percent-outline' as const },
  { key: 'retencion_10_nr_comun', file: '10_NO-RESIDENTES_SEC.COMUN_.pdf', icon: 'file-percent-outline' as const },
  { key: 'cuota_min_petroliferos', file: 'CUOTA-MIN.FISCAL_PETROLERA.pdf', icon: 'barrel-outline' as const },
  { key: 'cuota_min_comun', file: 'CUOTA-MIN.FISCAL_SEC.COMUN_.pdf', icon: 'office-building-outline' as const },
  { key: 'iva_destajo', file: 'I.V.A.-DESTAJO.pdf', icon: 'receipt' as const },
  { key: 'iva_real', file: 'I.V.A.-REAL.pdf', icon: 'receipt' as const },
  { key: 'imp_prod_petroleros_ivs', file: 'IMP.PROD_.PETROLEROS_IVS.pdf', icon: 'barrel' as const },
  { key: 'imp_prod_petroliferos_fmi', file: 'IMP.PROD_.PETROLIFEROS_FMI.pdf', icon: 'barrel' as const },
  { key: 'imp_salarios_petrolero', file: 'IMP.SUELDOS-Y-SALARIOS_PETROLERO.pdf', icon: 'account-cash-outline' as const },
  { key: 'imp_salarios_comun', file: 'IMP.SUELDOS-Y-SALARIOS_SEC.COMUN_.pdf', icon: 'account-cash-outline' as const },
  { key: 'impreso_comun', file: 'IMPRESO-COMUN.pdf', icon: 'file-document-outline' as const },
  { key: 'liquidacion', file: 'IMPRESO-DE-LIQUIDACION.pdf', icon: 'calculator-variant-outline' as const },
] as const;

function FormsSection({ t, colors }: { t: any; colors: any }) {
  const openForm = (file: string, label: string) => {
    const url = `${BASE_FORMS_URL}/${file}`;
    Linking.openURL(url).catch(() => {
      Alert.alert('Error', t('guide.forms.openError'));
    });
  };

  return (
    <View>
      <View style={{ paddingHorizontal: 16, paddingVertical: 12, backgroundColor: colors.secondaryContainer, marginHorizontal: 16, borderRadius: 12, marginBottom: 8 }}>
        <Text variant="bodySmall" style={{ color: colors.onSecondaryContainer, lineHeight: 20 }}>
          {t('guide.forms.info')}
        </Text>
      </View>

      {FORMS.map((form, i) => (
        <View key={form.key}>
          <List.Item
            title={t(`guide.forms.${form.key}`)}
            description="PDF"
            left={(props) => <List.Icon {...props} icon={form.icon} color={colors.primary} />}
            right={(props) => <List.Icon {...props} icon="open-in-new" color={colors.primary} />}
            onPress={() => openForm(form.file, t(`guide.forms.${form.key}`))}
          />
          {i < FORMS.length - 1 && <Divider style={{ marginLeft: 56 }} />}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function GuideScreen() {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const [section, setSection] = useState<Section>('steps');

  const buttons = [
    { value: 'steps' as Section, label: t('guide.tabs.steps'), icon: 'shoe-print' },
    { value: 'faq' as Section, label: t('guide.tabs.faq'), icon: 'help-circle-outline' },
    { value: 'forms' as Section, label: t('guide.tabs.forms'), icon: 'file-download-outline' },
  ];

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <Text variant="titleMedium" style={{ fontWeight: '600', color: colors.onSurface }}>
          {t('guide.title')}
        </Text>
      </View>

      <View style={{ paddingHorizontal: 16, paddingVertical: 12 }}>
        <SegmentedButtons
          value={section}
          onValueChange={(v) => setSection(v as Section)}
          buttons={buttons}
          density="small"
        />
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
        {section === 'steps' && <StepsSection t={t} colors={colors} />}
        {section === 'faq' && <FaqSection t={t} colors={colors} />}
        {section === 'forms' && <FormsSection t={t} colors={colors} />}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
  },
  stepCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
});
