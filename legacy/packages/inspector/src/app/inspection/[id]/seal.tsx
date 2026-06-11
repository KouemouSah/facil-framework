/**
 * Propose Seal Screen — Agent proposes sealing the business
 */

import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, RadioButton, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { extractApiError } from '@core/api/errors';
import { hapticHeavy, hapticError } from '@core/utils/haptics';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useInspectionDetail, useProposeSeal } from '@modules/inspections/services/inspections-hooks';
import type { SealReason } from '@modules/inspections/types/inspection.types';

const SEAL_REASONS: { value: SealReason; key: string }[] = [
  { value: 'non_paiement_apres_med', key: 'seal.reasons.non_paiement_apres_med' },
  { value: 'activite_non_autorisee', key: 'seal.reasons.activite_non_autorisee' },
  { value: 'fraude_fiscale', key: 'seal.reasons.fraude_fiscale' },
  { value: 'faux_documents', key: 'seal.reasons.faux_documents' },
  { value: 'refus_controle', key: 'seal.reasons.refus_controle' },
  { value: 'non_conformite_grave', key: 'seal.reasons.non_conformite_grave' },
  { value: 'decision_judiciaire', key: 'seal.reasons.decision_judiciaire' },
  { value: 'ordre_ministeriel', key: 'seal.reasons.ordre_ministeriel' },
];

export default function SealProposeScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const sealMutation = useProposeSeal(id ?? '');

  const [reason, setReason] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = useCallback(() => {
    if (!reason) {
      setError(t('seal.selectReason'));
      return;
    }

    // Double confirmation for critical action
    Alert.alert(
      t('seal.title'),
      t('seal.impact'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('seal.confirmSeal'),
          style: 'destructive',
          onPress: async () => {
            try {
              setError('');
              await sealMutation.mutateAsync({
                reason,
                notes: notes.trim() || undefined,
              });
              hapticHeavy();
              router.back();
            } catch (err) {
              hapticError();
              setError(extractApiError(err).message);
            }
          },
        },
      ],
    );
  }, [reason, notes, sealMutation, t]);

  if (isLoading || !inspection) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: custom.status.sealProposed as string, fontWeight: '700' }}>
            {t('seal.title')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Warning Banner */}
        <View style={[styles.warningBanner, { backgroundColor: `${custom.status.sealApproved}12` }]}>
          <MaterialCommunityIcons name="alert" size={20} color={custom.status.sealApproved as string} />
          <Text variant="bodyMedium" style={{ color: custom.status.sealApproved as string, flex: 1, marginLeft: 8 }}>
            {t('seal.impact')}
          </Text>
        </View>

        {/* Company */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={{ color: colors.onSurface }}>
            {inspection.company_name ?? '—'} • {inspection.company_nif}
          </Text>
        </View>
        <Divider />

        {/* Reason Selection */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('seal.reason')}
          </Text>
          <RadioButton.Group onValueChange={setReason} value={reason}>
            {SEAL_REASONS.map((r) => (
              <RadioButton.Item
                key={r.value}
                label={t(r.key)}
                value={r.value}
                mode="android"
                style={styles.radioItem}
                labelStyle={styles.radioLabel}
              />
            ))}
          </RadioButton.Group>
        </View>
        <Divider />

        {/* Notes */}
        <View style={styles.section}>
          <TextInput
            mode="flat"
            label={t('inspection.notes')}
            value={notes}
            onChangeText={setNotes}
            multiline
            numberOfLines={3}
            maxLength={2000}
            style={{ backgroundColor: 'transparent' }}
          />
        </View>

        {error ? (
          <Text variant="bodyMedium" style={{ color: colors.error, paddingHorizontal: 16 }}>{error}</Text>
        ) : null}

        <View style={styles.submitSection}>
          <Button
            mode="contained"
            icon="lock"
            onPress={handleSubmit}
            loading={sealMutation.isPending}
            disabled={sealMutation.isPending || !reason}
            buttonColor={custom.status.sealProposed as string}
            style={styles.submitButton}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('seal.propose')}
          </Button>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  content: { paddingBottom: 32 },
  warningBanner: { flexDirection: 'row', alignItems: 'center', padding: 12, margin: 16, borderRadius: 8 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 4 },
  radioItem: { paddingVertical: 2 },
  radioLabel: { fontSize: 14 },
  submitSection: { paddingHorizontal: 16, paddingTop: 16 },
  submitButton: { borderRadius: 8 },
});
