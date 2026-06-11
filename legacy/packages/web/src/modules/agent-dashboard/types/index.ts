/**
 * Agent Dashboard Types
 * Type definitions for generic agent dashboard menus and configuration
 *
 * @module agent-dashboard/types
 * @date 2025-01-14
 *
 * This module defines the menu structure for agent dashboards.
 * Each entity (CNEDOGE, DGT, ONRC, etc.) has its own menu configuration.
 */

import type { LucideIcon } from 'lucide-react';

// =============================================================================
// ENTITY CODES - Must match backend EntityCode enum
// =============================================================================

export type EntityCode =
  | 'CNEDOGE'           // Centro Nacional de Expedición de Documentos (parent entity)
  | 'CNEDOGE_PASAPORTE' // CNEDOGE department - Passports
  | 'CNEDOGE_RESIDENCIA'// CNEDOGE department - Residence permits
  | 'EXTRANJERIA'       // Dirección General de Extranjería
  | 'DGT'               // Dirección General de Tráfico (Licenses, Vehicles)
  | 'OFIVE'             // Oficina de Vehículos (CUVE)
  | 'ITV'               // Inspección Técnica de Vehículos
  | 'ONRC'              // Oficina Nacional de Registro de Contratos
  | 'MINFP'             // Ministerio de Función Pública
  | 'TESORO'            // Treasury (Trésor)
  | 'DGI'               // Dirección General de Impuestos (not yet implemented)
  | 'POLICIA'           // Policía Nacional - Certificados y verificaciones
  | 'GENERAL';          // Generic/fallback

// =============================================================================
// MINISTRY CODES - For ministry_agent dashboard aggregation
// =============================================================================
// Using actual ministry_code values from the database

export type MinistryCode =
  | 'M-009'   // MINISTERIO DE INTERIOR Y COOPERACIONES LOCALES - DGT, CNEDOGE
  | 'M-007';  // MINISTERIO DE HACIENDA ECONOMIA PLANIFICACIÓN E INVERSIONES - TESORO, DGI

// MINISTRY_ENTITIES mapping removed — now derived from backend (AgentProfileWithDetails.ministry_entities)

// =============================================================================
// WORKFLOW CODES - Must match backend WorkflowCode enum
// =============================================================================

export type WorkflowCode =
  // Pasaporte (CNEDOGE)
  | 'PASAPORTE_NUEVO'
  | 'PASAPORTE_RENOVACION'
  | 'PASAPORTE_PERDIDA'
  | 'PASAPORTE_ROBO'
  | 'PASAPORTE_DETERIORO'
  // Residencia (CNEDOGE + EXTRANJERIA)
  | 'RESIDENCIA_PRIMERA_VEZ'
  | 'RESIDENCIA_RENOVACION'
  | 'RESIDENCIA_DUPLICADO'
  | 'RESIDENCIA_CAMBIO_DATOS'
  | 'RESIDENCIA_REAGRUPACION'
  // Vehiculo (DGT + OFIVE + ITV)
  | 'VEHICULO_PRIMERA_MATRICULACION'
  | 'VEHICULO_TRANSFERENCIA'
  | 'VEHICULO_RENOVACION_CUVE'
  | 'VEHICULO_RENOVACION_ITV'
  | 'VEHICULO_DUPLICADO_PERMISO'
  | 'VEHICULO_DUPLICADO_CUVE'
  | 'VEHICULO_CAMBIO_CARACTERISTICAS'
  // Conducir (DGT)
  | 'CONDUCIR_NUEVO'
  | 'CONDUCIR_CANJE'
  | 'CONDUCIR_RENOVACION'
  | 'CONDUCIR_DUPLICADO'
  | 'CONDUCIR_EXTENSION'
  // Contrato (ONRC)
  | 'CONTRATO_OBRA'
  | 'CONTRATO_SERVICIO'
  | 'CONTRATO_SUMINISTRO'
  | 'CONTRATO_CONCESION'
  | 'CONTRATO_JOINT_VENTURE'
  | 'CONTRATO_ARRENDAMIENTO'
  | 'CONTRATO_OTRO'
  // Funcion Publica (MINFP)
  | 'FP_VERIFICACION_FUNCIONARIO'
  | 'FP_CARNET_FUNCIONARIO'
  | 'FP_PROMOCION_ADMINISTRATIVA'
  | 'FP_PERMISO_EXTRAORDINARIO'
  | 'FP_CERTIFICADO_ADMINISTRATIVO';

// =============================================================================
// MENU ITEM TYPES
// =============================================================================

/**
 * Single menu item (no children)
 */
export interface MenuSingleItem {
  id: string;
  titleKey: string;  // i18n key for translation
  href: string;
  icon: LucideIcon;
  badge?: number;
  permission?: string;  // Required permission to see this menu
  workflows?: WorkflowCode[];  // Workflows this menu handles
}

/**
 * Menu group with collapsible sub-items
 */
export interface MenuGroup {
  id: string;
  titleKey: string;
  icon: LucideIcon;
  items: MenuSingleItem[];
  permission?: string;  // Permission to see the entire group
}

/**
 * Union type for any menu item
 */
export type MenuItem = MenuSingleItem | MenuGroup;

/**
 * Type guard to check if item is a group
 */
export function isMenuGroup(item: MenuItem): item is MenuGroup {
  return 'items' in item && Array.isArray(item.items);
}

// =============================================================================
// ENTITY CONFIGURATION
// =============================================================================

/**
 * Menu source determines how menu permissions are resolved:
 * - 'workflow': Entity uses service_requests with workflow_code filtering
 * - 'module': Entity uses a dedicated module (treasury, declarations) without workflows
 */
export type MenuSource = 'workflow' | 'module';

/**
 * Data source for entity dashboard queries
 */
export type DataSource = 'service_requests' | 'service_payments' | 'tax_declarations';

/**
 * Configuration for an entity's agent dashboard
 */
export interface EntityDashboardConfig {
  entityCode: EntityCode;
  titleKey: string;  // i18n key for entity name
  icon: LucideIcon;
  basePath: string;  // Base URL path (e.g., '/dashboard/agent/cnedoge')
  menuItems: MenuItem[];
  workflows: WorkflowCode[];  // All workflows handled by this entity
  description?: string;

  /**
   * Menu source type - determines permission resolution strategy
   * - 'workflow': Uses service_requests.read, service_requests.validate, etc.
   * - 'module': Uses module-specific permissions (e.g., treasury.validate_payment)
   * @default 'workflow'
   */
  menuSource?: MenuSource;

  /**
   * Permission prefix for module-based entities
   * Used when menuSource is 'module' to construct full permission names
   * Example: 'treasury' → permissions like 'treasury.validate_payment'
   */
  modulePermissionPrefix?: string;

  /**
   * Data source table for dashboard queries
   * - 'service_requests': Standard workflow entities (CNEDOGE, DGT, etc.)
   * - 'service_payments': Treasury entity
   * - 'tax_declarations': DGI entity
   */
  dataSource?: DataSource;
}

// =============================================================================
// AGENT CONTEXT
// =============================================================================

/**
 * Current agent's context for dashboard
 */
export interface AgentDashboardContext {
  agentProfileId: string;
  userId: string;
  entityCode: EntityCode | null;
  entityId: string | null;
  entityName: string | null;
  entityLocationId: string | null;
  isMainOffice: boolean;
  locationName: string | null;
  ministryId: number | null;
  ministryName: string | null;
  isSupervisor: boolean;
  permissions: string[];
  specializations: string[];
}

// =============================================================================
// RE-EXPORT MENU CONFIG TYPES
// =============================================================================

export * from './menu-config';
