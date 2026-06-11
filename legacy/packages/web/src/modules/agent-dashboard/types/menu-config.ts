/**
 * Menu Configuration Types
 * Aligned with backend Pydantic models for dynamic menu/dashboard configuration
 *
 * @module agent-dashboard/types
 * @date 2026-01-19
 */

// =============================================================================
// MENU BADGE
// =============================================================================

export interface MenuBadge {
  type: 'count' | 'status';
  source: string;
}

// =============================================================================
// SUB-MENU ITEM
// =============================================================================

export interface SubMenuItem {
  id: string;
  titleKey: string;
  href: string;
  icon: string;
  permission?: string;
  badge?: MenuBadge;
}

// =============================================================================
// MENU ITEM
// =============================================================================

export interface DynamicMenuItem {
  id: string;
  titleKey: string;
  icon: string;
  href?: string;
  permission?: string;
  items?: SubMenuItem[];
}

// =============================================================================
// MENU CONFIG
// =============================================================================

export type MenuSource = 'workflow' | 'role' | 'custom';

export interface MenuConfig {
  version: string;
  source: MenuSource;
  menus: DynamicMenuItem[];
}

// =============================================================================
// WIDGET CONFIG
// =============================================================================

export type WidgetSize = 'small' | 'medium' | 'large' | 'full';

export interface WidgetConfig {
  id: string;
  visible: boolean;
  position: number;
  size: WidgetSize;
  customConfig?: Record<string, unknown>;
}

// =============================================================================
// DASHBOARD CONFIG
// =============================================================================

export type DashboardLayout = 'grid' | 'list' | 'custom';

export interface DashboardConfig {
  version: string;
  layout: DashboardLayout;
  widgets: WidgetConfig[];
}

// =============================================================================
// AGENT MENU CONFIG RESPONSE (from API)
// =============================================================================

export type EntityType = 'workflow' | 'module';

/** Display config for a single workflow (from workflow_display_config table) */
export interface WorkflowDisplayConfig {
  list_columns: string[];
  preview_sections: string[];
  labels: Record<string, string>;
}

export interface AgentMenuConfigResponse {
  agent_profile_id: string;
  entity_code: string | null;
  entity_name: string | null;
  entity_icon: string | null;
  entity_type: EntityType;
  role_code: string | null;
  available_workflows: string[];
  menu_config: MenuConfig;
  dashboard_config: DashboardConfig;
  permissions: string[];
  /** Display configs keyed by workflow_code — admin-configured column/section preferences */
  display_configs: Record<string, WorkflowDisplayConfig>;
  /** True if role.menu_config is NOT NULL in DB - for fallback detection */
  has_role_menu_config: boolean;
}

// =============================================================================
// CUSTOM SUB-ITEM (JSONB on workflow_menu_mapping)
// =============================================================================

export interface CustomSubItem {
  id: string;
  title_key: string;
  icon: string;
  action: string;
  filter_params: Record<string, string>;
  display_order: number;
  is_active: boolean;
}

// =============================================================================
// WORKFLOW MENU MAPPING (Admin)
// =============================================================================

export interface WorkflowMenuMapping {
  id: number;
  workflow_pattern: string;
  menu_group_id: string;
  menu_title_key: string;
  menu_icon: string;
  display_order: number;
  include_pending: boolean;
  include_validation: boolean;
  include_appointments: boolean;
  include_history: boolean;
  include_escalation: boolean;
  include_batch: boolean;
  custom_sub_items: CustomSubItem[];
  permission_prefix?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface WorkflowMenuMappingListResponse {
  items: WorkflowMenuMapping[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =============================================================================
// TYPE GUARDS
// =============================================================================

export function isDynamicMenuGroup(item: DynamicMenuItem): item is DynamicMenuItem & { items: SubMenuItem[] } {
  return Array.isArray(item.items) && item.items.length > 0;
}

export function isDynamicMenuLink(item: DynamicMenuItem): item is DynamicMenuItem & { href: string } {
  return typeof item.href === 'string' && item.href.length > 0;
}
