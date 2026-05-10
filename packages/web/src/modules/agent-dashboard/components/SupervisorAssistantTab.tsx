'use client';

/**
 * Supervisor Assistant Tab — AI chat for entity supervisors.
 *
 * Thin wrapper around AgentChatUI with supervisor-specific config:
 * quick actions for request stats, SLA, agents, workflows.
 * Uses the unified POST /agents/analyst/ask endpoint.
 */

import { useMemo } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import {
  BarChart3, Clock, Users, ListOrdered, TrendingUp,
  FileText, AlertTriangle, Sparkles, DollarSign,
  Search, FileCheck, Calendar,
} from 'lucide-react';
import { AgentChatUI } from '@/components/agent-chat';
import type { AgentChatConfig, AgentResponse } from '@/components/agent-chat';
import { analystApi } from '../services/analyst-api';
import type { AnalystBriefingResponse } from '../services/analyst-api';

// ── Entity accent colors ─────────────────────────────────────────────────────

const ENTITY_ACCENT: Record<string, string> = {
  CNEDOGE_PASAPORTE: 'bg-blue-100',
  CNEDOGE_RESIDENCIA: 'bg-indigo-100',
  DGT: 'bg-orange-100',
  MINFP: 'bg-teal-100',
  ONRC: 'bg-amber-100',
  OFIVE: 'bg-cyan-100',
  POLICIA: 'bg-rose-100',
  ITV: 'bg-lime-100',
  EXTRANJERIA: 'bg-violet-100',
  CNEDOGE: 'bg-sky-100',
  COMISARIA: 'bg-gray-100',
};

// ── Props ────────────────────────────────────────────────────────────────────

interface SupervisorAssistantTabProps {
  entityCode: string;
  entityName: string;
  isSupervisor?: boolean;
}

// ── Component ────────────────────────────────────────────────────────────────

export function SupervisorAssistantTab({ entityCode, entityName, isSupervisor = true }: SupervisorAssistantTabProps) {
  const t = useTranslations('agent.assistant');

  // Fetch auto-briefing
  const { data: briefing, isLoading: briefingLoading } = useQuery<AnalystBriefingResponse>({
    queryKey: ['analyst-briefing', entityCode],
    queryFn: () => analystApi.getBriefing(),
    staleTime: 2 * 60 * 1000, // 2 min
    retry: 1,
  });

  const mutation = useMutation<
    AgentResponse,
    Error,
    { question: string; previousContext?: { question: string; tools_used: string[] }; sessionId: string }
  >({
    mutationFn: async ({ question, previousContext, sessionId }) => {
      const raw = await analystApi.ask(question, previousContext, sessionId);
      return {
        answer: raw.answer,
        tools_used: raw.tools_used,
        data: raw.data,
        artifacts: raw.artifacts as AgentResponse['artifacts'],
      };
    },
  });

  const accentColor = ENTITY_ACCENT[entityCode] || 'bg-blue-100';

  const config: AgentChatConfig = useMemo(() => ({
    title: t('title', { entityName }),
    description: t('description'),
    placeholder: t('placeholder'),
    analyzingText: t('analyzingText'),
    analyzingDesc: t('analyzingDesc'),
    errorMessage: t('errorMessage'),
    emptyStateText: t('emptyStateText', { entityName }),
    emptyExamplesText: t('emptyExamplesText'),
    labels: {
      toolsUsed: t('toolsUsed'),
      retry: t('retry'),
      history: t('history'),
      quickActionsMenu: t('quickActionsMenu'),
      download: t('download'),
    },
    quickActions: isSupervisor ? [
      // Supervisor quick actions (team management, analytics)
      {
        label: t('quickActions.stats'),
        question: t('quickActions.statsQuestion'),
        icon: BarChart3,
      },
      {
        label: t('quickActions.sla'),
        question: t('quickActions.slaQuestion'),
        icon: Clock,
      },
      {
        label: t('quickActions.agents'),
        question: t('quickActions.agentsQuestion'),
        icon: Users,
      },
      {
        label: t('quickActions.pending'),
        question: t('quickActions.pendingQuestion'),
        icon: ListOrdered,
      },
      {
        label: t('quickActions.trends'),
        question: t('quickActions.trendsQuestion'),
        icon: TrendingUp,
      },
      {
        label: t('quickActions.rejections'),
        question: t('quickActions.rejectionsQuestion'),
        icon: AlertTriangle,
      },
      {
        label: t('quickActions.config'),
        question: t('quickActions.configQuestion'),
        icon: FileText,
      },
      {
        label: t('quickActions.tariffs'),
        question: t('quickActions.tariffsQuestion'),
        icon: DollarSign,
      },
    ] : [
      // Field agent quick actions (request processing, citizen lookup)
      {
        label: 'Mi cola de trabajo',
        question: 'Muestra mi cola de trabajo pendiente con prioridades',
        icon: ListOrdered,
      },
      {
        label: 'Buscar expediente',
        question: 'Buscar solicitud por referencia o NIF del ciudadano',
        icon: Search,
      },
      {
        label: 'Urgencias SLA',
        question: 'Cuales son los items con SLA critico?',
        icon: Clock,
      },
      {
        label: 'Verificar documentos',
        question: 'Estado de documentos de la solicitud',
        icon: FileCheck,
      },
      {
        label: 'Consultar tarifa',
        question: 'Cuanto cuesta este tramite con suplementos?',
        icon: DollarSign,
      },
      {
        label: 'Citas disponibles',
        question: 'Que citas estan disponibles esta semana?',
        icon: Calendar,
      },
      {
        label: 'Estadisticas',
        question: 'Estadisticas de mi entidad esta semana',
        icon: BarChart3,
      },
      {
        label: 'Procedimiento',
        question: 'Cuales son los pasos de este tramite?',
        icon: FileText,
      },
    ],
    mutation,
    accentColor,
    icon: Sparkles,
    briefing: briefing ? {
      briefing: briefing.briefing,
      priority: (briefing.priority as 'normal' | 'attention' | 'urgent') || 'normal',
      recommendations: briefing.recommendations,
    } : undefined,
    briefingLoading,
  }), [entityName, mutation, accentColor, briefing, briefingLoading, isSupervisor, t]);

  return <AgentChatUI config={config} />;
}

export default SupervisorAssistantTab;
