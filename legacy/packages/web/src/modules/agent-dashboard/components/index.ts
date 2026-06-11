/**
 * Agent Dashboard Components
 * @module agent-dashboard/components
 */

export { GenericAgentSidebar, MobileAgentSidebar, default } from './GenericAgentSidebar';
export { GenericEntityDashboard } from './GenericEntityDashboard';
export { AccessDenied } from './AccessDenied';
export { DynamicMenu } from './DynamicMenu';
export { DynamicDashboard } from './DynamicDashboard';
export type { WidgetData } from './DynamicDashboard';

// Widget components
export {
  UrgentRequestsWidget,
  TodayAppointmentsWidget,
  WorkflowDistributionWidget,
  AlertsWidget,
  WIDGET_REGISTRY,
  hasWidget,
  getWidget,
  renderWidget,
  WIDGET_SIZE_CLASSES,
  DEFAULT_ENTITY_WIDGETS,
} from './widgets';
export type { WidgetProps, WidgetComponent } from './widgets';

// Supervisor Assistant
export { SupervisorAssistantTab } from './SupervisorAssistantTab';

// Appointments components
export {
  AppointmentsPage,
  TodayTab,
  ScheduleTab,
  CalendarTab,
  AppointmentPreviewSheet,
} from './appointments';
