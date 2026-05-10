/**
 * Mission Planning Screen — Create and manage field missions
 */

import React, { useCallback, useState } from 'react';
import { Alert, FlatList, Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Checkbox, Chip, Divider, FAB, Modal, Portal, Text, TextInput } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import { extractApiError } from '@core/api/errors';
import { EmptyState } from '@components/ui/empty-state';
import { LoadingScreen } from '@components/ui/loading-screen';
import {
  useMissions,
  useCreateMission,
  useCompleteMission,
  useZoneSuggestions,
} from '@modules/supervisor/services/supervisor-hooks';
import type { Mission, ZoneSuggestion } from '@modules/supervisor/services/supervisor-api';

const STATUS_COLORS: Record<string, string> = {
  planned: '#1565C0',
  in_progress: '#F57F17',
  completed: '#2E7D32',
  cancelled: '#616161',
};

export default function MissionsScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  const { data, isLoading, refetch, isRefetching } = useMissions();
  const createMutation = useCreateMission();
  const completeMutation = useCompleteMission();
  const { data: suggestions } = useZoneSuggestions();

  const [showCreate, setShowCreate] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDate, setNewDate] = useState(new Date().toISOString().split('T')[0]);
  const [newNotes, setNewNotes] = useState('');
  const [selectedZones, setSelectedZones] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');

  const missions = data?.items ?? [];

  const handleCreate = useCallback(async () => {
    if (!newDate) return;
    setError('');
    try {
      await createMutation.mutateAsync({
        mission_date: newDate,
        title: newTitle.trim() || undefined,
        notes: newNotes.trim() || undefined,
        zone_ids: selectedZones.size > 0 ? Array.from(selectedZones) : undefined,
      });
      setShowCreate(false);
      setNewTitle('');
      setNewNotes('');
      setSelectedZones(new Set());
    } catch (err) {
      setError(extractApiError(err).message);
    }
  }, [newDate, newTitle, newNotes, createMutation]);

  const handleComplete = useCallback(
    (mission: Mission) => {
      Alert.alert(
        t('common.confirm'),
        `${mission.title ?? formatDate(mission.mission_date)}`,
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('common.confirm'),
            onPress: async () => {
              try {
                await completeMutation.mutateAsync({ id: mission.id });
              } catch (err) {
                Alert.alert(t('common.error'), extractApiError(err).message);
              }
            },
          },
        ],
      );
    },
    [completeMutation, t],
  );

  const renderMission = useCallback(
    ({ item }: { item: Mission }) => {
      const statusColor = STATUS_COLORS[item.status] ?? colors.onSurfaceVariant;
      const canComplete = item.status === 'in_progress' || item.status === 'planned';

      return (
        <Pressable
          onPress={() => router.push(`/supervisor/missions/${item.id}` as never)}
          style={({ pressed }) => [styles.missionItem, pressed && { backgroundColor: colors.surfaceVariant }]}
          android_ripple={{ color: colors.surfaceVariant }}
        >
          <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
          <View style={styles.missionBody}>
            <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }} numberOfLines={1}>
              {item.title ?? formatDate(item.mission_date)}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {formatDate(item.mission_date)} • {item.agents?.length ?? 0} {t('supervisor.agentStatus').toLowerCase()}
            </Text>
            {item.notes && (
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
                {item.notes}
              </Text>
            )}
          </View>
          <View style={styles.missionRight}>
            <Text variant="labelSmall" style={{ color: statusColor, fontWeight: '600' }}>
              {item.status}
            </Text>
            {canComplete && (
              <Button
                mode="text"
                compact
                icon="check"
                onPress={() => handleComplete(item)}
                textColor={colors.primary}
              >
                OK
              </Button>
            )}
          </View>
        </Pressable>
      );
    },
    [colors, handleComplete, t],
  );

  if (isLoading) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('supervisor.features.missionPlanning')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      {/* Zone suggestions */}
      {suggestions && suggestions.length > 0 && (
        <View style={[styles.suggestionsBar, { backgroundColor: colors.surfaceVariant }]}>
          <MaterialCommunityIcons name="lightbulb-outline" size={16} color={colors.primary} />
          <Text variant="bodySmall" style={{ color: colors.onSurface, marginLeft: 6, flex: 1 }}>
            {t('supervisor.features.missionPlanning')}: {suggestions.slice(0, 3).map((s) => s.zone_code).join(', ')}
          </Text>
        </View>
      )}

      <FlatList
        data={missions}
        keyExtractor={(item) => item.id}
        renderItem={renderMission}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: 28 }} />}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <EmptyState
            icon="map-marker-path"
            title={t('common.noData')}
            description={t('supervisor.noMissions', { defaultValue: 'No missions planned' })}
          />
        }
        contentContainerStyle={missions.length === 0 ? styles.emptyContainer : styles.listContent}
      />

      <FAB
        icon="plus"
        onPress={() => setShowCreate(true)}
        style={[styles.fab, { bottom: insets.bottom + 16 }]}
      />

      {/* Create Mission Modal */}
      <Portal>
        <Modal
          visible={showCreate}
          onDismiss={() => setShowCreate(false)}
          contentContainerStyle={[styles.modal, { backgroundColor: colors.surface }]}
        >
          <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700', marginBottom: 16 }}>
            {t('supervisor.features.missionPlanning')}
          </Text>
          <TextInput
            mode="outlined"
            label={t('inspection.date')}
            value={newDate}
            onChangeText={setNewDate}
            placeholder="YYYY-MM-DD"
            style={styles.input}
          />
          <TextInput
            mode="outlined"
            label={t('inspection.title', { defaultValue: 'Title' })}
            value={newTitle}
            onChangeText={setNewTitle}
            maxLength={200}
            style={styles.input}
          />
          <TextInput
            mode="outlined"
            label={t('inspection.notes')}
            value={newNotes}
            onChangeText={setNewNotes}
            multiline
            numberOfLines={3}
            maxLength={2000}
            style={styles.input}
          />
          {/* Zone selection */}
          {suggestions && suggestions.length > 0 && (
            <View style={styles.zoneSection}>
              <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant, marginBottom: 6 }}>
                {t('supervisor.zones', { defaultValue: 'Zones' })} ({selectedZones.size})
              </Text>
              <ScrollView style={{ maxHeight: 150 }}>
                {suggestions.map((z: ZoneSuggestion) => (
                  <Pressable
                    key={z.zone_id ?? z.zone_code}
                    style={styles.zoneRow}
                    onPress={() => {
                      setSelectedZones((prev) => {
                        const next = new Set(prev);
                        const key = z.zone_id ?? z.zone_code;
                        if (next.has(key)) next.delete(key); else next.add(key);
                        return next;
                      });
                    }}
                  >
                    <Checkbox
                      status={selectedZones.has(z.zone_id ?? z.zone_code) ? 'checked' : 'unchecked'}
                      color={colors.primary}
                    />
                    <View style={{ flex: 1 }}>
                      <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                        {z.zone_code} — {z.zone_name ?? ''}
                      </Text>
                      <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                        {z.suggested_priority ?? ''} • {z.pending_obligations_count ?? 0} pending
                      </Text>
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            </View>
          )}

          {error ? (
            <Text variant="bodySmall" style={{ color: colors.error, marginBottom: 8 }}>{error}</Text>
          ) : null}
          <View style={styles.modalActions}>
            <Button onPress={() => setShowCreate(false)}>{t('common.cancel')}</Button>
            <Button
              mode="contained"
              onPress={handleCreate}
              loading={createMutation.isPending}
              disabled={createMutation.isPending || !newDate}
            >
              {t('common.save')}
            </Button>
          </View>
        </Modal>
      </Portal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  suggestionsBar: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 10,
    borderRadius: 8,
  },
  listContent: { paddingBottom: 80 },
  emptyContainer: { flexGrow: 1 },
  missionItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16 },
  statusDot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  missionBody: { flex: 1, gap: 1 },
  missionRight: { alignItems: 'flex-end', gap: 4 },
  fab: { position: 'absolute', right: 16 },
  modal: { marginHorizontal: 24, padding: 24, borderRadius: 12, maxHeight: '85%' },
  input: { marginBottom: 12 },
  zoneSection: { marginBottom: 12 },
  zoneRow: { flexDirection: 'row', alignItems: 'center', minHeight: 44 },
  modalActions: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8, marginTop: 8 },
});
