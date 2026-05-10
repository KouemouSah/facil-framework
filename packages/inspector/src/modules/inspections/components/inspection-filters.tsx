import React, { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, SegmentedButtons, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@core/theme';
import type { InspectionStatus, InspectionResult } from '@modules/inspections/types/inspection.types';

interface FilterState {
  status?: InspectionStatus;
  result?: InspectionResult;
  sort_by?: 'inspection_date' | 'created_at' | 'payment_amount' | 'company_name' | 'status' | 'result';
  sort_dir?: 'asc' | 'desc';
}

interface Props {
  filters: FilterState;
  onApply: (filters: FilterState) => void;
  onClear: () => void;
}

export function InspectionFilters({ filters, onApply, onClear }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [local, setLocal] = useState<FilterState>(filters);

  const STATUS_OPTIONS = [
    { value: '', label: t('filters.all') },
    { value: 'in_progress', label: t('filters.inProgress') },
    { value: 'completed', label: t('filters.completed') },
    { value: 'mise_en_demeure', label: t('filters.notice') },
    { value: 'seal_proposed', label: t('filters.seal') },
  ];

  const SORT_OPTIONS = [
    { value: 'created_at', label: t('filters.date') },
    { value: 'company_name', label: t('filters.company') },
    { value: 'payment_amount', label: t('filters.amount') },
  ];

  return (
    <View style={[styles.container, { backgroundColor: colors.surface }]}>
      <Text variant="titleSmall" style={[styles.title, { color: colors.onSurface }]}>
        {t('filters.title')}
      </Text>

      {/* Status */}
      <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant, marginBottom: 4 }}>
        {t('inspection.status')}
      </Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
        {STATUS_OPTIONS.map((opt) => (
          <Button
            key={opt.value}
            mode={local.status === opt.value || (!local.status && !opt.value) ? 'contained' : 'outlined'}
            compact
            onPress={() => setLocal({ ...local, status: opt.value as InspectionStatus || undefined })}
            style={styles.chip}
            labelStyle={styles.chipLabel}
          >
            {opt.label}
          </Button>
        ))}
      </ScrollView>

      <Divider style={{ marginVertical: 12 }} />

      {/* Sort */}
      <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant, marginBottom: 4 }}>
        {t('filters.sortBy')}
      </Text>
      <SegmentedButtons
        value={local.sort_by ?? 'created_at'}
        onValueChange={(v) => setLocal({ ...local, sort_by: v as FilterState['sort_by'] })}
        buttons={SORT_OPTIONS}
        density="small"
        style={styles.segmented}
      />

      <View style={styles.dirRow}>
        <Button
          mode={local.sort_dir !== 'asc' ? 'contained' : 'outlined'}
          compact
          onPress={() => setLocal({ ...local, sort_dir: 'desc' })}
          style={styles.dirButton}
        >
          {t('filters.recent')}
        </Button>
        <Button
          mode={local.sort_dir === 'asc' ? 'contained' : 'outlined'}
          compact
          onPress={() => setLocal({ ...local, sort_dir: 'asc' })}
          style={styles.dirButton}
        >
          {t('filters.oldest')}
        </Button>
      </View>

      <Divider style={{ marginVertical: 12 }} />

      <View style={styles.actions}>
        <Button mode="text" onPress={onClear} textColor={colors.onSurfaceVariant}>
          {t('filters.clear')}
        </Button>
        <Button mode="contained" onPress={() => onApply(local)}>
          {t('filters.apply')}
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { padding: 16, borderTopLeftRadius: 16, borderTopRightRadius: 16 },
  title: { fontWeight: '700', marginBottom: 16 },
  chipRow: { flexDirection: 'row', marginBottom: 8 },
  chip: { marginRight: 6, borderRadius: 16 },
  chipLabel: { fontSize: 12 },
  segmented: { marginBottom: 8 },
  dirRow: { flexDirection: 'row', gap: 8 },
  dirButton: { flex: 1, borderRadius: 8 },
  actions: { flexDirection: 'row', justifyContent: 'space-between' },
});
