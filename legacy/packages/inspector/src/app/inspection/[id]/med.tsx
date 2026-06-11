/**
 * Mise en Demeure Screen — Issue formal notice
 */

import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAppTheme } from '@core/theme';
import { extractApiError } from '@core/api/errors';
import { hapticHeavy, hapticError } from '@core/utils/haptics';
import { appConfig } from '@core/config/app';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useInspectionDetail, useInspectionObligations, useMiseEnDemeure } from '@modules/inspections/services/inspections-hooks';
import { ObligationList } from '@modules/inspections/components/obligation-list';
import { formatDate } from '@core/utils/format';
import { LoadingScreen as ObligationsLoading } from '@components/ui/loading-screen';

export default function MiseEnDemeureScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const { data: obligations, isLoading: obligationsLoading } = useInspectionObligations(
    inspection?.license_id,
  );
  const medMutation = useMiseEnDemeure(id ?? '');

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deadlineHours, setDeadlineHours] = useState(String(appConfig.business.medDeadlineDefaultHours));
  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  const toggleObligation = (obId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(obId)) next.delete(obId);
      else next.add(obId);
      return next;
    });
  };

  const deadlineDate = new Date(Date.now() + Number(deadlineHours) * 60 * 60 * 1000);

  const handleSubmit = useCallback(() => {
    if (selected.size === 0) {
      setError(t('med.selectObligations'));
      return;
    }
    const hours = parseInt(deadlineHours, 10);
    if (isNaN(hours) || hours < appConfig.business.medDeadlineMinHours || hours > appConfig.business.medDeadlineMaxHours) {
      setError(t('med.deadlineRange', { min: appConfig.business.medDeadlineMinHours, max: appConfig.business.medDeadlineMaxHours }));
      return;
    }

    Alert.alert(
      t('med.title'),
      t('med.confirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          style: 'destructive',
          onPress: async () => {
            try {
              setError('');
              await medMutation.mutateAsync({
                obligation_ids: Array.from(selected),
                deadline_hours: hours,
                notes: notes.trim() || undefined,
              });
              hapticHeavy();
              router.back();
            } catch (err) {
              setError(extractApiError(err).message);
            }
          },
        },
      ],
    );
  }, [selected, deadlineHours, notes, medMutation, t]);

  if (isLoading || !inspection) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: custom.status.miseEnDemeure as string, fontWeight: '700' }}>
            {t('med.title')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Company info */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={{ color: colors.onSurface }}>
            {inspection.company_name ?? '—'}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {inspection.company_nif} • {formatDate(inspection.inspection_date)}
          </Text>
        </View>
        <Divider />

        {/* Obligations selection */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('med.selectObligations')} ({selected.size} {t('med.selected')})
          </Text>
          {obligationsLoading ? (
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('common.loading')}
            </Text>
          ) : obligations && obligations.length > 0 ? (
            <ObligationList
              obligations={obligations}
              selectable
              selected={selected}
              onToggle={toggleObligation}
            />
          ) : (
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('obligations.none')}
            </Text>
          )}
        </View>
        <Divider />

        {/* Deadline */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('med.deadline')}
          </Text>
          <TextInput
            mode="flat"
            value={deadlineHours}
            onChangeText={setDeadlineHours}
            keyboardType="numeric"
            right={<TextInput.Affix text="h" />}
            style={{ backgroundColor: 'transparent' }}
          />
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 4 }}>
            {t('obligations.dueDate')}: {formatDate(deadlineDate, 'dd/MM/yyyy HH:mm')}
          </Text>
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
            icon="alert-octagon"
            onPress={handleSubmit}
            loading={medMutation.isPending}
            disabled={medMutation.isPending || selected.size === 0}
            buttonColor={custom.status.miseEnDemeure as string}
            style={styles.submitButton}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('med.issue')}
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
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  submitSection: { paddingHorizontal: 16, paddingTop: 16 },
  submitButton: { borderRadius: 8 },
});
