'use client';

/**
 * Admin Assistant Tab — Thin wrapper around the unified AgentChatUI.
 *
 * Provides admin-specific config: quick actions, mutation.
 * The old 278-line card-based layout is replaced by the ChatGPT-like shared UI.
 */

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { useMutation } from '@tanstack/react-query';
import {
  BarChart3, Clock, Users, UserX, AlertTriangle, Sparkles,
} from 'lucide-react';
import { AgentChatUI } from '@/components/agent-chat';
import type { AgentChatConfig, AgentResponse } from '@/components/agent-chat';
import { adminAssistantApi } from '../services/api';

export function AdminAssistantTab() {
  const t = useTranslations('admin.agents');

  // Admin API already returns tools_used (snake_case) — matches AgentResponse directly
  const mutation = useMutation<
    AgentResponse,
    Error,
    { question: string; previousContext?: { question: string; tools_used: string[] }; sessionId: string }
  >({
    mutationFn: async ({ question, previousContext, sessionId }) => {
      const raw = await adminAssistantApi.askQuestion(question, previousContext, sessionId);
      return {
        answer: raw.answer,
        tools_used: raw.tools_used,
        data: raw.data,
        artifacts: [],
      };
    },
  });

  const config: AgentChatConfig = useMemo(() => ({
    title: t('assistantTitle'),
    description: t('assistantDesc'),
    placeholder: t('assistantPlaceholder'),
    analyzingText: t('assistantAnalyzing'),
    analyzingDesc: t('assistantAnalyzingDesc'),
    errorMessage: t('assistantError'),
    emptyStateText: t('assistantEmptyState'),
    emptyExamplesText: t('assistantEmptyExamples'),
    labels: {
      toolsUsed: t('assistantToolsUsed'),
      retry: t('assistantRetry'),
      history: 'Historial',
      quickActionsMenu: 'Consultas rapidas',
      download: t('assistantDownload'),
    },
    quickActions: [
      { label: t('assistantQuickActions.daySummary'), question: '¿Cual es el resumen operativo del dia? Analiza las alertas activas, la distribucion de carga y detecta cualquier anomalia.', icon: BarChart3 },
      { label: t('assistantQuickActions.inactiveAgents'), question: '¿Hay agentes inactivos? Lista los que no tienen actividad reciente y analiza si hay un patron.', icon: UserX },
      { label: t('assistantQuickActions.workloadDist'), question: 'Muestrame la distribucion de carga de trabajo entre todas las entidades. ¿Hay desequilibrios?', icon: Users },
      { label: t('assistantQuickActions.slaReport'), question: 'Dame un reporte de cumplimiento SLA. ¿Hay pagos en riesgo o vencidos? ¿Hay patrones de incumplimiento?', icon: Clock },
      { label: t('assistantQuickActions.anomalies'), question: 'Analiza todos los datos disponibles y detecta anomalias o patrones inusuales en el comportamiento de los agentes.', icon: AlertTriangle },
    ],
    mutation,
    accentColor: 'bg-purple-100',
    icon: Sparkles,
  }), [t, mutation]);

  return <AgentChatUI config={config} />;
}

export default AdminAssistantTab;
