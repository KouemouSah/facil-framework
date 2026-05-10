'use client';

/**
 * Treasury Analyst Tab — Thin wrapper around the unified AgentChatUI.
 *
 * Provides treasury-specific config: quick actions, briefing, mutation adapter.
 * The old 537-line Bloomberg layout is replaced by the ChatGPT-like shared UI.
 */

import { useMemo } from 'react';
import { useTranslations } from 'next-intl';
import { useMutation } from '@tanstack/react-query';
import {
  BarChart3, Clock, TrendingUp, Users, ShieldAlert,
  ArrowLeftRight, ListOrdered, Sparkles,
} from 'lucide-react';
import { AgentChatUI } from '@/components/agent-chat';
import type { AgentChatConfig, AgentResponse } from '@/components/agent-chat';
import { useTreasuryBriefing } from '../hooks';
import treasuryApi from '../services/api';

// ── Normalize Treasury response (camelCase → snake_case for tools_used) ──

function toAgentResponse(raw: {
  answer: string;
  toolsUsed: string[];
  data: Record<string, unknown>;
  artifacts?: AgentChatConfig['mutation'] extends never ? never : AgentResponse['artifacts'];
}): AgentResponse {
  return {
    answer: raw.answer,
    tools_used: raw.toolsUsed,
    data: raw.data,
    artifacts: raw.artifacts,
  };
}

export function TreasuryAnalystTab() {
  const t = useTranslations('treasury.analyst');
  const { data: briefing, isLoading: briefingLoading } = useTreasuryBriefing();

  // Adapted mutation: wraps the treasury API and normalizes response
  const mutation = useMutation<
    AgentResponse,
    Error,
    { question: string; previousContext?: { question: string; tools_used: string[] }; sessionId: string }
  >({
    mutationFn: async ({ question, previousContext, sessionId }) => {
      const raw = await treasuryApi.askAnalyst(
        question,
        previousContext ? { question: previousContext.question, toolsUsed: previousContext.tools_used } : undefined,
        sessionId,
      );
      return toAgentResponse(raw);
    },
  });

  const config: AgentChatConfig = useMemo(() => ({
    title: t('title'),
    description: t('description'),
    placeholder: t('placeholder'),
    analyzingText: t('analyzing'),
    analyzingDesc: t('analyzingDesc'),
    errorMessage: t('error'),
    emptyStateText: t('emptyState'),
    emptyExamplesText: t('emptyExamples'),
    labels: {
      toolsUsed: t('toolsUsed'),
      retry: t('retry'),
      history: t('historyLabel'),
      quickActionsMenu: t('quickActionsMenu'),
      recommendations: t('recommendations'),
      download: 'MD',
    },
    quickActions: [
      { label: t('quickActions.revenueSummary'), question: 'Resumen de ingresos del mes: montante total, transacciones, desglose por metodo de pago y servicio.', icon: BarChart3 },
      { label: t('quickActions.pendingSla'), question: 'Estado de pagos pendientes y alertas SLA. ¿Hay pagos vencidos o en riesgo? Detalle por urgencia.', icon: Clock },
      { label: t('quickActions.agentPerformance'), question: 'Rendimiento de los agentes de tesoreria: validaciones, rechazos, tiempo promedio y tasa SLA por agente.', icon: Users },
      { label: t('quickActions.anomalies'), question: 'Anomalias detectadas y recomendaciones. ¿Cuantas hay abiertas? ¿Hay patrones preocupantes?', icon: ShieldAlert },
      { label: t('quickActions.forecast'), question: 'Tendencia de ingresos de los ultimos 7 dias. ¿Hay patron al alza o a la baja?', icon: TrendingUp },
      { label: t('quickActions.entityComparison'), question: 'Comparacion de ingresos y volumenes entre entidades. ¿Cual genera mas revenue?', icon: ArrowLeftRight },
      { label: t('quickActions.rejectionAnalysis'), question: 'Analisis de rechazos: patrones por agente y motivo. ¿Hay agentes con tasa alta de rechazo?', icon: ListOrdered },
    ],
    briefing: briefing ? {
      briefing: briefing.briefing,
      priority: briefing.priority as 'normal' | 'attention' | 'urgent',
      recommendations: briefing.recommendations,
    } : null,
    briefingLoading,
    mutation,
    accentColor: 'bg-emerald-100',
    icon: Sparkles,
  }), [t, briefing, briefingLoading, mutation]);

  return <AgentChatUI config={config} />;
}

export default TreasuryAnalystTab;
