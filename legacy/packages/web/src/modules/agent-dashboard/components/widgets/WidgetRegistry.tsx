/**
 * Widget Registry
 * Maps widget IDs to React components for dynamic dashboard rendering
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

'use client';

import React from 'react';
import type { WidgetConfig } from '../../types/menu-config';
import type { EntityCode } from '../../types';

// Import widget components
import { UrgentRequestsWidget } from './UrgentRequestsWidget';
import { TodayAppointmentsWidget } from './TodayAppointmentsWidget';
import { WorkflowDistributionWidget } from './WorkflowDistributionWidget';
import { AlertsWidget } from './AlertsWidget';
import { PersonalStatsWidget } from './PersonalStatsWidget';
import { TeamWorkloadWidget } from './TeamWorkloadWidget';
import { EscalationsWidget } from './EscalationsWidget';
import { PendingPaymentsWidget } from './PendingPaymentsWidget';
import { AnomalySummaryWidget } from './AnomalySummaryWidget';
import { CalendarWeekWidget } from './CalendarWeekWidget';
import { CalendarSlotsWidget } from './CalendarSlotsWidget';
import { RecentActivityWidget } from './RecentActivityWidget';
import { OmsObligationsWidget } from './OmsObligationsWidget';

// =============================================================================
// TYPES
// =============================================================================

export interface WidgetProps {
  entityCode: EntityCode;
  config: WidgetConfig;
  className?: string;
}

export type WidgetComponent = React.ComponentType<WidgetProps>;

// =============================================================================
// WIDGET REGISTRY
// Maps widget IDs to their React components
// =============================================================================

export const WIDGET_REGISTRY: Record<string, WidgetComponent> = {
  // Urgent/Priority widgets
  urgent_requests: ({ entityCode, className }) => (
    <UrgentRequestsWidget entityCode={entityCode} className={className} />
  ),

  // Appointments widgets
  today_appointments: ({ entityCode, className }) => (
    <TodayAppointmentsWidget entityCode={entityCode} className={className} />
  ),

  // Distribution widgets
  workflow_distribution: ({ entityCode, className }) => (
    <WorkflowDistributionWidget entityCode={entityCode} className={className} />
  ),

  // Alerts widgets
  alerts: ({ entityCode, className }) => (
    <AlertsWidget entityCode={entityCode} className={className} />
  ),
  system_alerts: ({ entityCode, className }) => (
    <AlertsWidget entityCode={entityCode} className={className} />
  ),

  // Personal Performance widgets
  personal_stats: ({ className }) => (
    <PersonalStatsWidget className={className} />
  ),

  // Team Management widgets (for supervisors)
  team_workload: ({ entityCode, className }) => (
    <TeamWorkloadWidget entityCode={entityCode} className={className} />
  ),

  // Escalation widgets (for supervisors)
  escalations: ({ entityCode, className }) => (
    <EscalationsWidget entityCode={entityCode} className={className} />
  ),

  // Treasury widgets
  pending_payments: ({ className }) => (
    <PendingPaymentsWidget className={className} />
  ),
  in_progress_payments: ({ className }) => (
    <PendingPaymentsWidget className={className} statusFilter="agent_reviewing" titleKey="widgets.inProgressPayments" />
  ),
  completed_payments: ({ className }) => (
    <PendingPaymentsWidget className={className} statusFilter="completed" titleKey="widgets.completedPayments" />
  ),

  // OMS / bundle collection widgets (agent_ayuntamiento, agent_camara, agent_min_*)
  // These IDs exist in roles.dashboard_config but were missing from the registry,
  // so the dashboard rendered nothing and every stat card fell back to 0.
  // Aliased to PendingPaymentsWidget with the appropriate statusFilter so each
  // entity-scoped agent sees their own assigned payments — the backend
  // /dashboard/widgets/pending-payments endpoint already filters by
  // assigned_agent_id (P8.2-B1.4).
  oms_pending_validations: ({ className }) => (
    <PendingPaymentsWidget className={className} titleKey="widgets.omsPendingValidations" />
  ),
  oms_validated_today: ({ className }) => (
    <PendingPaymentsWidget
      className={className}
      statusFilter="completed"
      titleKey="widgets.omsValidatedToday"
    />
  ),
  oms_overdue_alerts: ({ entityCode, className }) => (
    <AlertsWidget entityCode={entityCode} className={className} />
  ),
  oms_compliance_summary: ({ entityCode, className }) => (
    <AlertsWidget entityCode={entityCode} className={className} />
  ),

  // OMS obligation processing widgets (agent_min_* roles)
  // These IDs are in roles.dashboard_config for MIN_* entities.
  // They process obligations (post-payment), not payments — data comes
  // from /oms/queue/stats (license_obligations + assignments), not service_payments.
  oms_pending_processing: ({ className }) => (
    <OmsObligationsWidget variant="pending" className={className} />
  ),
  oms_processed_today: ({ className }) => (
    <OmsObligationsWidget variant="completed" className={className} />
  ),
  oms_documents_pending: ({ className }) => (
    <OmsObligationsWidget variant="documents" className={className} />
  ),
  oms_ministry_stats: ({ className }) => (
    <OmsObligationsWidget variant="ministry" className={className} />
  ),

  // OMS Supervisor widgets (supervisor_ayuntamiento, supervisor_camara, supervisor_min_*)
  // These IDs are in roles.dashboard_config for supervisor roles.
  oms_team_overview: ({ className }) => (
    <OmsObligationsWidget variant="ministry" className={className} />
  ),
  oms_pending_escalations: ({ entityCode, className }) => (
    <EscalationsWidget entityCode={entityCode} className={className} />
  ),
  oms_performance_stats: ({ className }) => (
    <OmsObligationsWidget variant="completed" className={className} />
  ),

  anomaly_summary: ({ className }) => (
    <AnomalySummaryWidget className={className} />
  ),

  // Escalation aliases
  my_escalations: ({ entityCode, className }) => (
    <EscalationsWidget entityCode={entityCode} className={className} />
  ),

  // Activity widget
  recent_activity: ({ entityCode, className }) => (
    <RecentActivityWidget entityCode={entityCode} className={className} />
  ),

  // Calendar widgets
  calendar_week: ({ entityCode, className }) => (
    <CalendarWeekWidget entityCode={entityCode} className={className} />
  ),
  calendar_slots: ({ entityCode, className }) => (
    <CalendarSlotsWidget entityCode={entityCode} className={className} />
  ),
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Check if a widget ID has a registered component
 */
export function hasWidget(widgetId: string): boolean {
  return widgetId in WIDGET_REGISTRY;
}

/**
 * Get widget component by ID
 */
export function getWidget(widgetId: string): WidgetComponent | null {
  return WIDGET_REGISTRY[widgetId] || null;
}

/**
 * Render a widget by ID with props
 */
export function renderWidget(
  widgetId: string,
  entityCode: EntityCode,
  config: WidgetConfig,
  className?: string
): React.ReactNode | null {
  const Widget = getWidget(widgetId);
  if (!Widget) {
    console.warn(`[WidgetRegistry] Unknown widget ID: ${widgetId}`);
    return null;
  }

  return (
    <Widget
      key={widgetId}
      entityCode={entityCode}
      config={config}
      className={className}
    />
  );
}

// =============================================================================
// SIZE CLASSES - Consistent with DynamicDashboard
// =============================================================================

export const WIDGET_SIZE_CLASSES: Record<string, string> = {
  small: 'col-span-1',
  medium: 'col-span-1 md:col-span-2',
  large: 'col-span-1 md:col-span-2 lg:col-span-3',
  full: 'col-span-full',
};

// =============================================================================
// DEFAULT WIDGET CONFIGS
// Fallback configurations when dashboard_config is not defined
// =============================================================================

export const DEFAULT_ENTITY_WIDGETS: WidgetConfig[] = [
  { id: 'urgent_requests', visible: true, position: 1, size: 'medium' },
  { id: 'today_appointments', visible: true, position: 2, size: 'medium' },
  { id: 'workflow_distribution', visible: true, position: 3, size: 'medium' },
  { id: 'alerts', visible: true, position: 4, size: 'medium' },
];

export default WIDGET_REGISTRY;
