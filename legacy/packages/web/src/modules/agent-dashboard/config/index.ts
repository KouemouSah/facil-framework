/**
 * Agent Dashboard Configuration
 *
 * entity-menus.ts has been REMOVED (P0-2).
 * All menu configuration now comes dynamically from backend API (GET /menu-config/me).
 *
 * Entity-specific filter configs are in entity-filters.ts.
 * Workflow codes come from backend (availableWorkflows), NOT from static config.
 *
 * @module agent-dashboard/config
 */

export {
  ENTITY_FILTER_CONFIGS,
  ENTITY_WORKFLOW_TITLES,
  WORKFLOW_CODE_LABELS,
  buildEffectiveFilters,
  buildWorkflowFilterOptions,
  resolveTypeLabel,
} from './entity-filters';
export type {
  FilterOption,
  FilterDef,
  TypeLabelConfig,
  EntityFilterConfig,
} from './entity-filters';
