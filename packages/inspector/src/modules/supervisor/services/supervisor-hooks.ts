/**
 * Supervisor Hooks — Analytics, Missions, Export
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supervisorApi, type Mission } from './supervisor-api';

const KEYS = {
  performance: (period: string) => ['supervisor', 'performance', period] as const,
  zones: (period: string) => ['supervisor', 'zones', period] as const,
  trends: (period: string) => ['supervisor', 'trends', period] as const,
  priorityZones: ['supervisor', 'priority-zones'] as const,
  missions: ['supervisor', 'missions'] as const,
  mission: (id: string) => ['supervisor', 'mission', id] as const,
  zoneSuggestions: ['supervisor', 'zone-suggestions'] as const,
};

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export function useAgentPerformance(dateFrom?: string, dateTo?: string) {
  const period = `${dateFrom ?? 'all'}_${dateTo ?? 'all'}`;
  return useQuery({
    queryKey: KEYS.performance(period),
    queryFn: () => supervisorApi.getAgentPerformance({
      date_from: dateFrom,
      date_to: dateTo,
    }),
    staleTime: 5 * 60_000,
  });
}

export function useZoneAnalytics(dateFrom?: string, dateTo?: string) {
  const period = `${dateFrom ?? 'all'}_${dateTo ?? 'all'}`;
  return useQuery({
    queryKey: KEYS.zones(period),
    queryFn: () => supervisorApi.getZoneAnalytics({
      date_from: dateFrom,
      date_to: dateTo,
    }),
    staleTime: 5 * 60_000,
  });
}

export function useTrends(dateFrom?: string, dateTo?: string, granularity = 'daily') {
  const period = `${dateFrom ?? 'all'}_${dateTo ?? 'all'}_${granularity}`;
  return useQuery({
    queryKey: KEYS.trends(period),
    queryFn: () => supervisorApi.getTrends({
      date_from: dateFrom,
      date_to: dateTo,
      granularity,
    }),
    staleTime: 5 * 60_000,
  });
}

export function usePriorityZones() {
  return useQuery({
    queryKey: KEYS.priorityZones,
    queryFn: () => supervisorApi.getPriorityZones(10),
    staleTime: 10 * 60_000,
  });
}

// ---------------------------------------------------------------------------
// Missions
// ---------------------------------------------------------------------------

export function useMissions(params?: { date_from?: string; date_to?: string; status?: string }) {
  return useQuery({
    queryKey: [...KEYS.missions, params],
    queryFn: () => supervisorApi.listMissions(params),
    staleTime: 2 * 60_000,
  });
}

export function useCreateMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { mission_date: string; title?: string; notes?: string; zone_ids?: string[] }) =>
      supervisorApi.createMission(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}

export function useCompleteMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) =>
      supervisorApi.completeMission(id, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}

export function useZoneSuggestions(enabled = true) {
  return useQuery({
    queryKey: KEYS.zoneSuggestions,
    queryFn: () => supervisorApi.suggestZones(),
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useMissionDetail(id: string) {
  return useQuery({
    queryKey: KEYS.mission(id),
    queryFn: () => supervisorApi.getMission(id),
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useAgentsAvailability(missionDate: string, entityLocationId?: string) {
  return useQuery({
    queryKey: ['supervisor', 'agents-availability', missionDate, entityLocationId],
    queryFn: () => supervisorApi.getAgentsAvailability(missionDate, entityLocationId),
    enabled: !!missionDate,
    staleTime: 2 * 60_000,
  });
}

export function useAssignAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, agents }: {
      missionId: string;
      agents: Array<{ agent_id: string; agent_profile_id: string; target_inspections?: number }>;
    }) => supervisorApi.assignAgents(missionId, agents),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}

export function useRemoveAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, agentId }: { missionId: string; agentId: string }) =>
      supervisorApi.removeAgent(missionId, agentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}

export function useUpdateAgentStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, agentId, status, reason }: {
      missionId: string; agentId: string; status: string; reason?: string;
    }) => supervisorApi.updateAgentStatus(missionId, agentId, status, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}

export function useAutoAssign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ missionId, targetTotal }: { missionId: string; targetTotal?: number }) =>
      supervisorApi.autoAssign(missionId, targetTotal),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.missions });
    },
  });
}
