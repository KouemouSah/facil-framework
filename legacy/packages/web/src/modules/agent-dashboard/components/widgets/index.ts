/**
 * Widgets Module Exports
 *
 * @module agent-dashboard/components/widgets
 * @date 2026-01-26
 */

// Widget components
export { UrgentRequestsWidget } from './UrgentRequestsWidget';
export { TodayAppointmentsWidget } from './TodayAppointmentsWidget';
export { WorkflowDistributionWidget } from './WorkflowDistributionWidget';
export { AlertsWidget } from './AlertsWidget';
export { PersonalStatsWidget } from './PersonalStatsWidget';
export { TeamWorkloadWidget } from './TeamWorkloadWidget';
export { EscalationsWidget } from './EscalationsWidget';
export { PendingPaymentsWidget } from './PendingPaymentsWidget';
export { AnomalySummaryWidget } from './AnomalySummaryWidget';
export { CalendarWeekWidget } from './CalendarWeekWidget';
export { CalendarSlotsWidget } from './CalendarSlotsWidget';

// Widget registry
export {
  WIDGET_REGISTRY,
  hasWidget,
  getWidget,
  renderWidget,
  WIDGET_SIZE_CLASSES,
  DEFAULT_ENTITY_WIDGETS,
  type WidgetProps,
  type WidgetComponent,
} from './WidgetRegistry';
