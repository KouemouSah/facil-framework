/**
 * Entity-specific filter configurations for agent dashboard
 *
 * BACKEND-DRIVEN ARCHITECTURE:
 * - workflowCodes come from backend via GET /menu-config/me → availableWorkflows
 * - WORKFLOW_CODE_LABELS maps every known workflow code to an i18n label key
 * - Entities WITHOUT explicit config auto-get a workflowCode filter when they have >1 workflow
 * - Only entities with SPECIALIZED filters (e.g., pasaporte's solicitudType/motivo)
 *   need explicit config here
 *
 * Adding a new workflow code:
 *   1. Add the code to entities.workflow_codes in the DB → filter auto-appears
 *   2. (Optional) Add label to WORKFLOW_CODE_LABELS for translated display
 *
 * @module agent-dashboard/config/entity-filters
 */

// =============================================================================
// TYPES
// =============================================================================

export interface FilterOption {
  value: string;
  /** i18n key relative to 'agent' namespace, OR raw label if isRawLabel=true */
  labelKey: string;
  /** If true, labelKey is a raw display string (not an i18n key) */
  isRawLabel?: boolean;
}

export interface FilterDef {
  /** API parameter name — must match useEntityServiceRequests option key */
  key: string;
  /** i18n key for the placeholder text */
  placeholderKey: string;
  /** Tailwind width class */
  width: string;
  /** Static options (for specialized filters like solicitudType, motivo) */
  options?: FilterOption[];
  /** Auto-generate options from availableWorkflows + WORKFLOW_CODE_LABELS */
  autoFromWorkflows?: boolean;
  /** Only show when another filter has a specific value */
  showWhen?: { filterKey: string; value: string };
}

export interface TypeLabelConfig {
  /** Primary request field to read for the type label */
  primaryField: string;
  /** Map of primary field values to i18n keys (relative to 'agent') */
  labels: Record<string, string>;
  /** Optional secondary field (e.g., 'motivo') that overrides primary */
  secondaryField?: string;
  /** Map of secondary field values (UPPERCASED) to i18n keys */
  secondaryLabels?: Record<string, string>;
}

export interface EntityFilterConfig {
  /** Filter definitions to render in the UI */
  filters: FilterDef[];
  /** Config for the "Tipo" column — only needed for specialized entities.
   *  Entities without typeLabel use WORKFLOW_CODE_LABELS as universal fallback. */
  typeLabel?: TypeLabelConfig;
}

// =============================================================================
// WORKFLOW CODE → i18n LABEL MAP (universal)
// =============================================================================

/**
 * Maps every known workflow code to its i18n label key (relative to 'agent' namespace).
 * Used for:
 * - Auto-generated filter options
 * - Universal type label fallback in resolveTypeLabel()
 *
 * If a code is not in this map, it gets a formatted fallback (e.g., "Primera Vez").
 */
export const WORKFLOW_CODE_LABELS: Record<string, string> = {
  // Pasaporte
  PASAPORTE_NUEVO: 'filters.nuevo',
  PASAPORTE_RENOVACION: 'filters.renovacion',
  PASAPORTE_PERDIDA: 'filters.perdida',
  PASAPORTE_ROBO: 'filters.robo',
  PASAPORTE_DETERIORO: 'filters.deterioro',
  // Residencia
  RESIDENCIA_PRIMERA_VEZ: 'filters.primeraVez',
  RESIDENCIA_RENOVACION: 'filters.renovacion',
  RESIDENCIA_DUPLICADO: 'filters.duplicado',
  RESIDENCIA_CAMBIO_DATOS: 'filters.cambioDatos',
  RESIDENCIA_REAGRUPACION: 'filters.reagrupacion',
  // Conducir
  CONDUCIR_NUEVO: 'filters.nuevo',
  CONDUCIR_CANJE: 'filters.canje',
  CONDUCIR_RENOVACION: 'filters.renovacion',
  CONDUCIR_DUPLICADO: 'filters.duplicado',
  CONDUCIR_EXTENSION: 'filters.extension',
  // Vehiculo
  VEHICULO_PRIMERA_MATRICULACION: 'filters.primeraMatriculacion',
  VEHICULO_TRANSFERENCIA: 'filters.transferencia',
  VEHICULO_RENOVACION_CUVE: 'filters.renovacionCuve',
  VEHICULO_RENOVACION_ITV: 'filters.renovacionItv',
  VEHICULO_DUPLICADO_PERMISO: 'filters.duplicadoPermiso',
  VEHICULO_DUPLICADO_CUVE: 'filters.duplicadoCuve',
  VEHICULO_CAMBIO_CARACTERISTICAS: 'filters.cambioCaracteristicas',
  // Contrato
  CONTRATO_OBRA: 'filters.obra',
  CONTRATO_SERVICIO: 'filters.servicio',
  CONTRATO_SUMINISTRO: 'filters.suministro',
  CONTRATO_CONCESION: 'filters.concesion',
  CONTRATO_JOINT_VENTURE: 'filters.jointVenture',
  CONTRATO_ARRENDAMIENTO: 'filters.arrendamiento',
  CONTRATO_OTRO: 'filters.otro',
  // Función Pública
  FP_VERIFICACION_FUNCIONARIO: 'filters.verificacion',
  FP_CARNET_FUNCIONARIO: 'filters.carnet',
  FP_PROMOCION_ADMINISTRATIVA: 'filters.promocion',
  FP_PERMISO_EXTRAORDINARIO: 'filters.permisoExtraordinario',
  FP_CERTIFICADO_ADMINISTRATIVO: 'filters.certificado',
  // Visados
  VISADO_ALTERNATIVO: 'filters.visadoAlternativo',
  SALIDA_VISADO_VENCIDO: 'filters.salidaVisadoVencido',
  PRORROGA_VISADO: 'filters.prorrogaVisado',
  PERMANENCIA_EXTRANJERIA: 'filters.permanencia',
};

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Format a workflow code as human-readable text.
 * Strips the family prefix and title-cases the rest.
 * Example: "VEHICULO_PRIMERA_MATRICULACION" → "Primera Matriculacion"
 */
function formatWorkflowCode(code: string): string {
  const parts = code.split('_');
  if (parts.length > 1) {
    return parts
      .slice(1)
      .map(p => p.charAt(0) + p.slice(1).toLowerCase())
      .join(' ');
  }
  return code;
}

/**
 * Build filter options from availableWorkflows + WORKFLOW_CODE_LABELS.
 * Returns [{ all }, ...workflow options] with i18n keys for known codes
 * and formatted fallback for unknown codes.
 */
export function buildWorkflowFilterOptions(
  availableWorkflows: string[],
): FilterOption[] {
  return [
    { value: 'all', labelKey: 'filters.allWorkflowTypes' },
    ...availableWorkflows.map(code => {
      const labelKey = WORKFLOW_CODE_LABELS[code];
      if (labelKey) {
        return { value: code, labelKey };
      }
      // Unknown code: use formatted text as raw label
      return {
        value: code,
        labelKey: formatWorkflowCode(code),
        isRawLabel: true,
      };
    }),
  ];
}

/**
 * Build the effective filter list for an entity.
 * - If entity has explicit config with autoFromWorkflows filters, resolve their options
 * - If entity has no config but >1 workflows, auto-generate a workflowCode filter
 * - Otherwise return empty array (no entity-specific filters)
 */
export function buildEffectiveFilters(
  entityCode: string,
  availableWorkflows: string[],
): FilterDef[] {
  const config = ENTITY_FILTER_CONFIGS[entityCode];

  if (config?.filters) {
    // Explicit config — resolve autoFromWorkflows options
    return config.filters.map(filter => {
      if (filter.autoFromWorkflows && !filter.options) {
        return {
          ...filter,
          options: buildWorkflowFilterOptions(availableWorkflows),
        };
      }
      return filter;
    });
  }

  // No explicit config — auto-generate workflowCode filter if multiple workflows
  if (availableWorkflows.length > 1) {
    return [{
      key: 'workflowCode',
      placeholderKey: 'filters.workflowType',
      width: 'w-[180px]',
      options: buildWorkflowFilterOptions(availableWorkflows),
    }];
  }

  return [];
}

// =============================================================================
// CONFIGURATIONS — ONLY entities with SPECIALIZED filters
// =============================================================================

/**
 * Explicit filter configs. Most entities DON'T need an entry here —
 * they get auto-generated workflowCode filters from availableWorkflows.
 *
 * Add an entry ONLY when the entity needs non-workflowCode filters
 * (e.g., solicitudType, motivo) or custom typeLabel logic.
 */
export const ENTITY_FILTER_CONFIGS: Record<string, EntityFilterConfig> = {
  CNEDOGE_PASAPORTE: {
    filters: [
      {
        key: 'solicitudType',
        placeholderKey: 'filters.type',
        width: 'w-[160px]',
        options: [
          { value: 'all', labelKey: 'filters.allTypes' },
          { value: 'expedicion', labelKey: 'filters.expedicion' },
          { value: 'renovacion', labelKey: 'filters.renovacion' },
        ],
      },
      {
        key: 'motivo',
        placeholderKey: 'filters.motivo',
        width: 'w-[160px]',
        showWhen: { filterKey: 'solicitudType', value: 'renovacion' },
        options: [
          { value: 'all', labelKey: 'filters.allMotivos' },
          { value: 'vencimiento', labelKey: 'filters.vencimiento' },
          { value: 'perdida', labelKey: 'filters.perdida' },
          { value: 'robo', labelKey: 'filters.robo' },
          { value: 'deterioro', labelKey: 'filters.deterioro' },
        ],
      },
    ],
    typeLabel: {
      primaryField: 'solicitudType',
      labels: {
        expedicion: 'filters.nuevo',
      },
      secondaryField: 'motivo',
      secondaryLabels: {
        VENCIMIENTO: 'filters.renovacion',
        PERDIDA: 'filters.perdida',
        ROBO: 'filters.robo',
        DETERIORO: 'filters.deterioro',
      },
    },
  },
  // NOTE: CNEDOGE_RESIDENCIA removed — auto workflowCode filter + WORKFLOW_CODE_LABELS
  // handles both filtering and type label display automatically.
};

// =============================================================================
// WORKFLOW GROUP TITLES
// =============================================================================

/** Maps ENTITY_CODE (UPPER_SNAKE) to i18n key for workflow group title */
export const ENTITY_WORKFLOW_TITLES: Record<string, string> = {
  DGT: 'nav.driverLicenses',
  OFIVE: 'nav.vehicles',
  ONRC: 'nav.contracts',
  EXTRANJERIA: 'nav.residences',
  POLICIA: 'nav.certificates',
  MINFP: 'nav.civilServants',
  ITVE: 'nav.inspections',
};

// =============================================================================
// TYPE LABEL RESOLVER
// =============================================================================

/**
 * Resolve the "Tipo" column label for a service request.
 *
 * Resolution order:
 * 1. Entity's explicit TypeLabelConfig (for specialized entities like pasaporte)
 * 2. WORKFLOW_CODE_LABELS universal map (for all workflow-based entities)
 * 3. Formatted workflowCode fallback (strip prefix, title-case)
 *
 * @param entityCode - UPPER_SNAKE entity code
 * @param request - Request data with workflowCode/solicitudType/motivo
 * @param t - i18n translate function (agent namespace)
 * @returns Translated label string
 */
export function resolveTypeLabel(
  entityCode: string,
  request: { workflowCode?: string; solicitudType?: string; motivo?: string | null },
  t: (key: string) => string,
): string {
  const config = ENTITY_FILTER_CONFIGS[entityCode]?.typeLabel;

  // 1. Explicit typeLabel config (specialized entities)
  if (config) {
    // Check secondary field first (override, e.g., motivo in pasaporte)
    if (config.secondaryField && config.secondaryLabels) {
      const secValue = (request as Record<string, unknown>)[config.secondaryField] as string;
      if (secValue) {
        const labelKey = config.secondaryLabels[secValue.toUpperCase()];
        if (labelKey) return t(labelKey);
      }
    }

    // Check primary field
    const priValue = (request as Record<string, unknown>)[config.primaryField] as string;
    if (priValue) {
      const labelKey = config.labels[priValue];
      if (labelKey) return t(labelKey);
    }

    return priValue || '-';
  }

  // 2. Universal fallback: WORKFLOW_CODE_LABELS
  const code = request.workflowCode;
  if (code) {
    const labelKey = WORKFLOW_CODE_LABELS[code];
    if (labelKey) return t(labelKey);
    // 3. Format code as readable text
    return formatWorkflowCode(code);
  }

  return '-';
}
