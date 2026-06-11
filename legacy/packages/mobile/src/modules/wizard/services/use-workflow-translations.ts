/**
 * useWorkflowTranslations — Fetches workflow-category translations from backend
 *
 * Uses React Query to cache GET /translations/system/export/workflow for 1 hour.
 * Exposes `tw(keyCode, fallbackEs)` that returns the translated string for the
 * current app language (es/fr/en).
 *
 * Key code patterns:
 *   workflow.name.{CODE}                — Workflow service names
 *   workflow.step.{normalized_title}    — Step titles
 *   workflow.option.{workflow}.{value}  — Option labels
 *   workflow.option.{workflow}.{value}.desc — Option descriptions
 *   workflow.motivo.{MOTIVO}            — Motivo labels
 *   workflow.motivo.{MOTIVO}.desc       — Motivo descriptions
 *   workflow.label.{key}               — Generic UI labels
 */

import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { getCurrentLanguage } from '@core/i18n';
import type { SupportedLanguage } from '@core/i18n';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Backend returns: { [key_code]: { es: string, fr: string, en: string } } */
type TranslationEntry = Record<'es' | 'fr' | 'en', string>;
type TranslationMap = Record<string, TranslationEntry>;

export interface UseWorkflowTranslationsReturn {
  /**
   * Translate a workflow key code.
   *
   * @param keyCode - The translation key (e.g. 'workflow.step.pago_tasas')
   * @param fallbackEs - Spanish fallback if key not found (optional, defaults to keyCode)
   * @returns Translated string in current language, or fallback
   */
  tw: (keyCode: string, fallbackEs?: string) => string;

  /** Whether translations are still loading */
  isLoading: boolean;

  /** Whether translations were loaded successfully */
  isReady: boolean;

  /** Raw translation map (for advanced use) */
  translations: TranslationMap;
}

// ---------------------------------------------------------------------------
// Normalizer: title_es → key_code suffix
// ---------------------------------------------------------------------------

/**
 * Normalize a Spanish title to match a workflow.step.* key code.
 *
 * Examples:
 *   "Pago de Tasas"         → "pago_tasas"
 *   "Verificar Datos (1/3)" → "verificar_datos_1_3"
 *   "Confirmación y Envío"  → "confirmacion_envio"
 */
function normalizeTitleToKey(titleEs: string): string {
  return titleEs
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip accents
    .replace(/[()]/g, '')            // remove parens
    .replace(/[/]/g, '_')            // slash to underscore
    .replace(/\s+de\s+la\s+/g, '_')  // "de la" → _
    .replace(/\s+del\s+/g, '_')      // "del" → _
    .replace(/\s+de\s+/g, '_')       // "de" → _
    .replace(/\s+y\s+/g, '_')        // "y" → _
    .replace(/\s+/g, '_')            // spaces to underscores
    .replace(/_+/g, '_')             // collapse multiple underscores
    .replace(/^_|_$/g, '');          // trim leading/trailing underscores
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fetch and use workflow translations from the backend.
 *
 * The endpoint is GET /translations/system/export/workflow
 * Returns { key_code: { es, fr, en } }
 */
export function useWorkflowTranslations(): UseWorkflowTranslationsReturn {
  const { data, isLoading, isSuccess } = useQuery<TranslationMap>({
    queryKey: ['workflow-translations'],
    queryFn: () => apiGet<TranslationMap>(API_ENDPOINTS.translations.systemWorkflow),
    staleTime: 60 * 60 * 1000, // 1 hour
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
    retry: 2,
    refetchOnWindowFocus: false,
  });

  const translations = data ?? {};
  const lang = getCurrentLanguage();

  /**
   * Resolve a translation for a given key code.
   * Tries the key directly, then falls back to the ES value.
   */
  const tw = useCallback(
    (keyCode: string, fallbackEs?: string): string => {
      const entry = translations[keyCode];
      if (entry) {
        return entry[lang as SupportedLanguage] || entry.es || fallbackEs || keyCode;
      }
      // If language is Spanish or no translation exists, return the fallback
      if (lang === 'es' && fallbackEs) return fallbackEs;
      return fallbackEs || keyCode;
    },
    [translations, lang],
  );

  return useMemo(
    () => ({
      tw,
      isLoading,
      isReady: isSuccess && !!data,
      translations,
    }),
    [tw, isLoading, isSuccess, data, translations],
  );
}

/**
 * Helper to build a step title key code from the Spanish title.
 * Usage: `tw(stepTitleKey("Pago de Tasas"), "Pago de Tasas")`
 */
export function stepTitleKey(titleEs: string): string {
  return `workflow.step.${normalizeTitleToKey(titleEs)}`;
}

/**
 * Helper to build a workflow name key code.
 * The workflowCode passed here is the root workflow family (e.g. "PASAPORTE"),
 * not the full code (e.g. "PASAPORTE_NUEVO").
 */
export function workflowNameKey(workflowCode: string): string {
  // Extract the root workflow family from codes like "PASAPORTE_NUEVO"
  // Map known prefixes
  const rootCode = extractWorkflowRoot(workflowCode);
  return `workflow.name.${rootCode}`;
}

/**
 * Extract the root workflow family from a full workflow code.
 *
 * PASAPORTE_NUEVO → PASAPORTE
 * CONDUCIR_CANJE → CONDUCIR
 * FP_VERIFICACION_FUNCIONARIO → FP_VERIFICACION_FUNCIONARIO (no split, full code is the key)
 * CONTRATO_OBRA → CONTRATO
 * VEHICULO_PRIMERA_MATRICULACION → MATRICULACION (matches backend name key)
 */
function extractWorkflowRoot(code: string): string {
  // Known root mappings for codes that don't follow simple prefix pattern
  const KNOWN_ROOTS: Record<string, string> = {
    // Pasaporte
    PASAPORTE_NUEVO: 'PASAPORTE',
    PASAPORTE_RENOVACION: 'PASAPORTE',
    PASAPORTE_PERDIDA: 'PASAPORTE',
    PASAPORTE_ROBO: 'PASAPORTE',
    PASAPORTE_DETERIORO: 'PASAPORTE',
    // Conducir
    CONDUCIR_NUEVO: 'CONDUCIR',
    CONDUCIR_CANJE: 'CONDUCIR',
    CONDUCIR_RENOVACION: 'CONDUCIR',
    CONDUCIR_DUPLICADO: 'CONDUCIR',
    CONDUCIR_EXTENSION: 'CONDUCIR',
    // Contrato
    CONTRATO_OBRA: 'CONTRATO',
    CONTRATO_SERVICIO: 'CONTRATO',
    CONTRATO_SUMINISTRO: 'CONTRATO',
    CONTRATO_CONCESION: 'CONTRATO',
    CONTRATO_JOINT_VENTURE: 'CONTRATO',
    CONTRATO_ARRENDAMIENTO: 'CONTRATO',
    CONTRATO_OTRO: 'CONTRATO',
    // Residencia
    RESIDENCIA_PRIMERA_VEZ: 'RESIDENCIA',
    RESIDENCIA_RENOVACION: 'RESIDENCIA',
    // Tramites visado
    PRORROGA_VISADO: 'TRAMITES_VISADO',
    VISADO_ALTERNATIVO: 'TRAMITES_VISADO',
    PERMANENCIA_EXTRANJERIA: 'TRAMITES_VISADO',
    SALIDA_VISADO_VENCIDO: 'TRAMITES_VISADO',
    // Vehiculos - matriculacion
    VEHICULO_PRIMERA_MATRICULACION: 'MATRICULACION',
    VEHICULO_TRANSFERENCIA: 'MATRICULACION',
    // Vehiculos - inspeccion
    VEHICULO_RENOVACION_CUVE: 'INSPECCION',
    VEHICULO_RENOVACION_ITV: 'INSPECCION',
    // Vehiculos - duplicado
    VEHICULO_DUPLICADO_PERMISO: 'DUPLICADO_VEHICULO',
    VEHICULO_DUPLICADO_CUVE: 'DUPLICADO_VEHICULO',
    VEHICULO_CAMBIO_CARACTERISTICAS: 'MATRICULACION',
  };

  if (KNOWN_ROOTS[code]) return KNOWN_ROOTS[code];

  // FP_ prefixed codes map to themselves
  if (code.startsWith('FP_')) return code;

  // BUNDLE_PAYMENT maps to itself
  if (code === 'BUNDLE_PAYMENT') return code;

  // Fallback: return as-is
  return code;
}

/**
 * Build option label key for a workflow.
 * @param workflowFamily - e.g. 'pasaporte', 'conducir'
 * @param optionValue - e.g. 'NUEVO', 'CANJE'
 */
export function optionLabelKey(workflowFamily: string, optionValue: string): string {
  return `workflow.option.${workflowFamily.toLowerCase()}.${optionValue}`;
}

/**
 * Build option description key for a workflow.
 */
export function optionDescKey(workflowFamily: string, optionValue: string): string {
  return `workflow.option.${workflowFamily.toLowerCase()}.${optionValue}.desc`;
}

/**
 * Build motivo key.
 */
export function motivoKey(motivoValue: string): string {
  return `workflow.motivo.${motivoValue}`;
}

/**
 * Build motivo description key.
 */
export function motivoDescKey(motivoValue: string): string {
  return `workflow.motivo.${motivoValue}.desc`;
}
