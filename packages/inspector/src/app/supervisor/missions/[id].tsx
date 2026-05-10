/**
 * Mission Detail — View mission, manage agents, complete
 *
 * Supervisor can: add agents (from availability list), remove agents,
 * mark absent, auto-assign, and complete the mission.
 */

import React, { useCallback, useState } from 'react';
import { Alert, FlatList, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Checkbox, Chip, Divider, Text } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import { extractApiError } from '@core/api/errors';
import { LoadingScreen } from '@components/ui/loading-screen';
import {
  useMissionDetail,
  useCompleteMission,
  useAgentsAvailability,
  useAssignAgents,
  useRemoveAgent,
  useUpdateAgentStatus,
  useAutoAssign,
} from '@modules/supervisor/services/supervisor-hooks';
import type { MissionAgent, AgentAvailability } from '@modules/supervisor/services/supervisor-api';

const AGENT_STATUS_COLORS: Record<string, string> = {
  assigned: '#1565C0',
  active: '#2E7D32',
  completed: '#616161',
  absent: '#C62828',
};

export default function MissionDetailScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: mission, isLoading } = useMissionDetail(id ?? '');
  const completeMutation = useCompleteMission();
  const assignMutation = useAssignAgents();
  const removeMutation = useRemoveAgent();
  const statusMutation = useUpdateAgentStatus();
  const autoAssignMutation = useAutoAssign();

  const [showAddAgents, setShowAddAgents] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());

  // Fetch available agents when "Add" panel is open
  const { data: availableAgents } = useAgentsAvailability(
    mission?.mission_date ?? '',
    mission?.entity_location_id,
  );

  const canModify = mission?.status === 'planned' || mission?.status === 'in_progress';
  const canComplete = mission?.status === 'in_progress';
  const canAddAgents = canModify;

  // --- Handlers ---

  const handleComplete = useCallback(() => {
    if (!id) return;
    Alert.alert(
      t('common.confirm'),
      t('supervisor.completeMission', { defaultValue: 'Complete this mission?' }),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          onPress: async () => {
            try {
              await completeMutation.mutateAsync({ id });
              router.back();
            } catch (err) {
              Alert.alert(t('common.error'), extractApiError(err).message);
            }
          },
        },
      ],
    );
  }, [id, completeMutation, t]);

  const handleAssignSelected = useCallback(async () => {
    if (!id || !availableAgents || selectedAgents.size === 0) return;
    const agents = availableAgents
      .filter((a: AgentAvailability) => selectedAgents.has(a.agent_id))
      .map((a: AgentAvailability) => ({
        agent_id: a.agent_id,
        agent_profile_id: a.agent_profile_id,
        target_inspections: 10,
      }));
    try {
      await assignMutation.mutateAsync({ missionId: id, agents });
      setSelectedAgents(new Set());
      setShowAddAgents(false);
    } catch (err) {
      Alert.alert(t('common.error'), extractApiError(err).message);
    }
  }, [id, availableAgents, selectedAgents, assignMutation, t]);

  const handleRemoveAgent = useCallback(
    (agent: MissionAgent) => {
      if (!id) return;
      Alert.alert(
        t('common.confirm'),
        `${t('supervisor.removeAgent', { defaultValue: 'Remove' })} ${agent.agent_name}?`,
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('supervisor.removeAgent', { defaultValue: 'Remove' }),
            style: 'destructive',
            onPress: async () => {
              try {
                await removeMutation.mutateAsync({ missionId: id, agentId: agent.agent_id });
              } catch (err) {
                Alert.alert(t('common.error'), extractApiError(err).message);
              }
            },
          },
        ],
      );
    },
    [id, removeMutation, t],
  );

  const handleMarkAbsent = useCallback(
    (agent: MissionAgent) => {
      if (!id) return;
      Alert.alert(
        t('supervisor.markAbsent', { defaultValue: 'Mark absent' }),
        agent.agent_name,
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('supervisor.markAbsent', { defaultValue: 'Mark absent' }),
            onPress: async () => {
              try {
                await statusMutation.mutateAsync({
                  missionId: id,
                  agentId: agent.agent_id,
                  status: 'absent',
                });
              } catch (err) {
                Alert.alert(t('common.error'), extractApiError(err).message);
              }
            },
          },
        ],
      );
    },
    [id, statusMutation, t],
  );

  const handleAutoAssign = useCallback(async () => {
    if (!id) return;
    try {
      const result = await autoAssignMutation.mutateAsync({ missionId: id, targetTotal: 50 });
      if (result.agents_proposed === 0) {
        Alert.alert(
          t('common.info', { defaultValue: 'Info' }),
          t('supervisor.noAvailableAgents', { defaultValue: 'No available agents for this date and location.' }),
        );
      } else {
        Alert.alert(
          t('supervisor.autoAssign', { defaultValue: 'Auto-assign' }),
          `${result.agents_proposed} ${t('supervisor.agentsProposed', { defaultValue: 'agents proposed' })}`,
          [
            { text: t('common.cancel'), style: 'cancel' },
            {
              text: t('common.confirm'),
              onPress: async () => {
                const agents = result.proposals.map((p) => ({
                  agent_id: p.agent_id,
                  agent_profile_id: p.agent_profile_id,
                  target_inspections: p.target_inspections,
                }));
                try {
                  await assignMutation.mutateAsync({ missionId: id, agents });
                } catch (err) {
                  Alert.alert(t('common.error'), extractApiError(err).message);
                }
              },
            },
          ],
        );
      }
    } catch (err) {
      Alert.alert(t('common.error'), extractApiError(err).message);
    }
  }, [id, autoAssignMutation, assignMutation, t]);

  if (isLoading || !mission) return <LoadingScreen />;

  const agents: MissionAgent[] = mission.agents ?? [];

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

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Mission info */}
        <View style={styles.section}>
          <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700' }}>
            {mission.title ?? formatDate(mission.mission_date)}
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 }}>
            <Chip compact textStyle={{ fontSize: 11 }} style={{ backgroundColor: `${AGENT_STATUS_COLORS[mission.status] ?? colors.primary}20` }}>
              {mission.status}
            </Chip>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {formatDate(mission.mission_date)}
            </Text>
          </View>
          {mission.notes && (
            <Text variant="bodyMedium" style={{ color: colors.onSurface, marginTop: 8 }}>
              {mission.notes}
            </Text>
          )}
        </View>
        <Divider />

        {/* Agents section */}
        <View style={styles.section}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
              {t('supervisor.agentStatus')} ({agents.length})
            </Text>
            {canAddAgents && (
              <View style={{ flexDirection: 'row', gap: 4 }}>
                <Button
                  mode="text"
                  icon="robot"
                  compact
                  onPress={handleAutoAssign}
                  loading={autoAssignMutation.isPending}
                >
                  {t('supervisor.autoAssign', { defaultValue: 'Auto' })}
                </Button>
                <Button mode="text" icon="plus" compact onPress={() => setShowAddAgents(!showAddAgents)}>
                  {t('common.add', { defaultValue: 'Add' })}
                </Button>
              </View>
            )}
          </View>

          {/* Add agents panel (collapsible) */}
          {showAddAgents && availableAgents && (
            <View style={[styles.addPanel, { backgroundColor: `${colors.primary}08` }]}>
              <Text variant="labelMedium" style={{ color: colors.primary, marginBottom: 6 }}>
                {t('supervisor.availableAgents', { defaultValue: 'Available agents' })} ({availableAgents.filter((a: AgentAvailability) => a.is_available).length})
              </Text>
              <ScrollView style={{ maxHeight: 180 }}>
                {availableAgents
                  .filter((a: AgentAvailability) => a.is_available)
                  .map((a: AgentAvailability) => (
                    <Pressable
                      key={a.agent_id}
                      style={styles.agentCheckRow}
                      onPress={() => {
                        setSelectedAgents((prev) => {
                          const next = new Set(prev);
                          if (next.has(a.agent_id)) next.delete(a.agent_id); else next.add(a.agent_id);
                          return next;
                        });
                      }}
                    >
                      <Checkbox status={selectedAgents.has(a.agent_id) ? 'checked' : 'unchecked'} color={colors.primary} />
                      <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1 }}>
                        {a.agent_name}
                      </Text>
                    </Pressable>
                  ))}
              </ScrollView>
              <Button
                mode="contained"
                compact
                onPress={handleAssignSelected}
                disabled={selectedAgents.size === 0 || assignMutation.isPending}
                loading={assignMutation.isPending}
                style={{ marginTop: 8, borderRadius: 6 }}
              >
                {t('supervisor.assignSelected', { defaultValue: 'Assign' })} ({selectedAgents.size})
              </Button>
            </View>
          )}

          {/* Agent list */}
          {agents.length === 0 ? (
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('supervisor.noAgents', { defaultValue: 'No agents assigned' })}
            </Text>
          ) : (
            agents.map((agent) => (
              <View key={agent.agent_id}>
                <View style={styles.agentRow}>
                  <View style={[styles.statusDot, { backgroundColor: AGENT_STATUS_COLORS[agent.status ?? 'assigned'] ?? colors.primary }]} />
                  <View style={{ flex: 1, marginLeft: 8 }}>
                    <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                      {agent.agent_name}
                    </Text>
                    <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                      {agent.status ?? 'assigned'}
                      {agent.target_inspections != null ? ` • ${agent.target_inspections} insp.` : ''}
                      {agent.assigned_zones?.length ? ` • ${agent.assigned_zones.join(', ')}` : ''}
                    </Text>
                  </View>
                  {canModify && agent.status !== 'completed' && agent.status !== 'absent' && (
                    <Pressable onPress={() => handleMarkAbsent(agent)} style={{ padding: 4 }}>
                      <MaterialCommunityIcons name="account-cancel" size={20} color={custom?.status?.miseEnDemeure ?? '#E65100'} />
                    </Pressable>
                  )}
                  {mission.status === 'planned' && (
                    <Pressable onPress={() => handleRemoveAgent(agent)} style={{ padding: 4, marginLeft: 4 }}>
                      <MaterialCommunityIcons name="close-circle" size={20} color={colors.error} />
                    </Pressable>
                  )}
                </View>
                <Divider style={{ marginLeft: 28 }} />
              </View>
            ))
          )}
        </View>

        {/* Complete button */}
        {canComplete && (
          <View style={styles.section}>
            <Button
              mode="contained"
              icon="check-circle"
              onPress={handleComplete}
              loading={completeMutation.isPending}
              disabled={completeMutation.isPending}
              style={styles.completeButton}
            >
              {t('inspection.complete')}
            </Button>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  scrollContent: { paddingBottom: 32 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  agentRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10 },
  agentCheckRow: { flexDirection: 'row', alignItems: 'center', minHeight: 40 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  addPanel: { padding: 12, borderRadius: 8, marginBottom: 12 },
  completeButton: { borderRadius: 8 },
});
