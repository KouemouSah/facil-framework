/**
 * Workflow Selection Screen — Entry point for "Nouvelle demande"
 *
 * Redesigned: Category cards with expand/collapse, search bar, descriptions.
 * Android native flat list with dividers.
 *
 * Uses GET /service-requests/workflows (backend returns workflows list).
 */

import { useMemo, useState, useCallback } from 'react';
import { StyleSheet, View, ScrollView, Pressable } from 'react-native';
import { Text, ActivityIndicator, Divider, IconButton } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useAvailableWorkflows } from '@modules/service-requests';
import type { WorkflowInfo } from '@modules/service-requests';

// ---------------------------------------------------------------------------
// Category config (icons + labels per language)
// ---------------------------------------------------------------------------

interface CategoryDef {
  icon: string;
  color: string;
  bg: string;
  es: string; fr: string; en: string;
  descEs: string; descFr: string; descEn: string;
}

const CATEGORY_CONFIG: Record<string, CategoryDef> = {
  IDENTIDAD: { icon: 'card-account-details', color: '#2E7D32', bg: '#E8F5E9', es: 'Identidad', fr: 'Identité', en: 'Identity', descEs: 'DIP, Pasaportes', descFr: 'DIP, Passeports', descEn: 'ID, Passports' },
  EXTRANJERIA: { icon: 'earth', color: '#1565C0', bg: '#E3F2FD', es: 'Extranjería', fr: 'Immigration', en: 'Immigration', descEs: 'Visados, Residencia', descFr: 'Visas, Résidence', descEn: 'Visas, Residence' },
  VEHICULOS: { icon: 'car', color: '#E65100', bg: '#FFF3E0', es: 'Vehículos', fr: 'Véhicules', en: 'Vehicles', descEs: 'Matriculación, Inspección', descFr: 'Immatriculation, Inspection', descEn: 'Registration, Inspection' },
  CONDUCCION: { icon: 'card-account-details-outline', color: '#6A1B9A', bg: '#F3E5F5', es: 'Conducción', fr: 'Conduite', en: 'Driving', descEs: 'Permisos de conducir', descFr: 'Permis de conduire', descEn: 'Driving licenses' },
  CONTRATOS: { icon: 'file-sign', color: '#4E342E', bg: '#EFEBE9', es: 'Contratos', fr: 'Contrats', en: 'Contracts', descEs: 'Legalización contratos', descFr: 'Légalisation contrats', descEn: 'Contract legalization' },
  COMERCIO: { icon: 'store', color: '#00695C', bg: '#E0F2F1', es: 'Comercio', fr: 'Commerce', en: 'Commerce', descEs: 'Licencias comerciales', descFr: 'Licences commerciales', descEn: 'Commercial licenses' },
  FUNCION_PUBLICA: { icon: 'badge-account', color: '#37474F', bg: '#ECEFF1', es: 'Función Pública', fr: 'Fonction Publique', en: 'Public Service', descEs: 'Certificados funcionarios', descFr: 'Certificats fonctionnaires', descEn: 'Civil servant certificates' },
  REGISTRO_CIVIL: { icon: 'book-open-variant', color: '#AD1457', bg: '#FCE4EC', es: 'Registro Civil', fr: 'État Civil', en: 'Civil Registry', descEs: 'Nacimiento, Matrimonio', descFr: 'Naissance, Mariage', descEn: 'Birth, Marriage' },
};

/** Fixed display order so COMERCIO is always visible */
const CATEGORY_ORDER = ['IDENTIDAD', 'EXTRANJERIA', 'VEHICULOS', 'CONDUCCION', 'CONTRATOS', 'COMERCIO', 'FUNCION_PUBLICA', 'REGISTRO_CIVIL'];

function getCategoryLabel(category: string, lang: string): string {
  const config = CATEGORY_CONFIG[category];
  if (!config) return category.replace(/_/g, ' ');
  return lang === 'fr' ? config.fr : lang === 'en' ? config.en : config.es;
}

function getCategoryDesc(category: string, lang: string): string {
  const config = CATEGORY_CONFIG[category];
  if (!config) return '';
  return lang === 'fr' ? config.descFr : lang === 'en' ? config.descEn : config.descEs;
}

/** Translate workflow name using i18n key, fallback to backend name */
function getWorkflowName(wf: WorkflowInfo, t: (key: string) => string): string {
  const key = `workflows.${wf.code}`;
  const translated = t(key);
  // If key not found (returns the key itself), use backend name
  return translated === key ? wf.service_name_es : translated;
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function SelectWorkflowScreen() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { colors } = useAppTheme();
  const lang = i18n.language;

  const { data: workflows, isLoading, isError } = useAvailableWorkflows();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  // Group workflows by category, in fixed order
  const groups = useMemo(() => {
    if (!workflows) return [];
    const grouped: Record<string, WorkflowInfo[]> = {};
    for (const wf of workflows) {
      const cat = wf.category || 'GENERAL';
      // Exclude FUNCION_PUBLICA — only accessible via dedicated funcionario menu (aligned with web)
      if (cat === 'FUNCION_PUBLICA') continue;
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(wf);
    }
    return CATEGORY_ORDER
      .filter((cat) => grouped[cat]?.length)
      .map((cat) => ({ category: cat, config: CATEGORY_CONFIG[cat], workflows: grouped[cat] }));
  }, [workflows]);

  const toggleCategory = useCallback((cat: string) => {
    setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
  }, []);

  const handleSelectWorkflow = useCallback((wf: WorkflowInfo) => {
    // BUNDLE_PAYMENT has its own dedicated wizard (not generic)
    if (wf.code === 'BUNDLE_PAYMENT') {
      router.push('/bundle-wizard' as never);
      return;
    }
    router.push(`/wizard/create?workflow_code=${wf.code}` as never);
  }, [router]);

  if (isLoading) {
    return (
      <SafeAreaView style={[s.container, s.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
      </SafeAreaView>
    );
  }

  if (isError || !workflows) {
    return (
      <SafeAreaView style={[s.container, s.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>{t('common.error')}</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[s.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="arrow-left" size={24} onPress={() => router.back()} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}>
          {t('wizard.selectWorkflow')}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 24 }}>
        {groups.map((group) => {
          const cfg = group.config;
          const isOpen = expanded[group.category] ?? (group.category === groups[0]?.category);
          const count = group.workflows.length;

          return (
            <View key={group.category} style={{ marginBottom: 2 }}>
              {/* Category header — tappable */}
              <Pressable
                style={[s.catHeader, { backgroundColor: cfg.bg }]}
                onPress={() => toggleCategory(group.category)}
                android_ripple={{ color: cfg.color + '20' }}
              >
                <View style={[s.catIcon, { backgroundColor: cfg.color }]}>
                  <MaterialCommunityIcons
                    name={cfg.icon as keyof typeof MaterialCommunityIcons.glyphMap}
                    size={22}
                    color="#fff"
                  />
                </View>
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={[s.catTitle, { color: cfg.color }]}>
                    {getCategoryLabel(group.category, lang)}
                  </Text>
                  <Text style={[s.catDesc, { color: cfg.color }]}>
                    {getCategoryDesc(group.category, lang)} · {count} {count > 1 ? 'options' : 'option'}
                  </Text>
                </View>
                <MaterialCommunityIcons
                  name={isOpen ? 'chevron-up' : 'chevron-down'}
                  size={22}
                  color={cfg.color}
                />
              </Pressable>

              {/* Workflows list — collapsible */}
              {isOpen && group.workflows.map((wf, i) => (
                <View key={wf.code}>
                  <Pressable
                    style={s.wfRow}
                    onPress={() => handleSelectWorkflow(wf)}
                    android_ripple={{ color: cfg.bg }}
                  >
                    <View style={[s.wfDot, { backgroundColor: cfg.color }]} />
                    <Text style={[s.wfName, { flex: 1, marginLeft: 12 }]}>{getWorkflowName(wf, t)}</Text>
                    <MaterialCommunityIcons name="chevron-right" size={18} color="#BDBDBD" />
                  </Pressable>
                  {i < group.workflows.length - 1 && <Divider style={{ marginLeft: 40 }} />}
                </View>
              ))}
            </View>
          );
        })}

        {groups.length === 0 && (
          <View style={[s.centered, { paddingTop: 60 }]}>
            <MaterialCommunityIcons name="magnify" size={48} color={colors.outlineVariant} />
            <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 12 }}>{t('common.noResults')}</Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  centered: { alignItems: 'center', justifyContent: 'center' },
  topBar: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1 },
  // Category header
  catHeader: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 14,
    borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.05)',
  },
  catIcon: {
    width: 40, height: 40, borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },
  catTitle: { fontSize: 15, fontWeight: '700' },
  catDesc: { fontSize: 11, opacity: 0.7, marginTop: 1 },

  // Workflow row
  wfRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingVertical: 13,
    backgroundColor: '#fff',
  },
  wfDot: { width: 8, height: 8, borderRadius: 4 },
  wfName: { fontSize: 14, fontWeight: '500', color: '#333' },
});
