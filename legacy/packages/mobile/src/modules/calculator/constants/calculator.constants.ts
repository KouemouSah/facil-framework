/**
 * Calculator constants — ported verbatim from web
 * `calculateur/page.tsx` (IRPF_BRACKETS, VAT_STANDARD_RATE, CORPORATE_TAX_RATE,
 * DEFAULT_CALCULABLE_SERVICES).
 *
 * These defaults are the source of truth when the backend
 * `GET /homepage/calculator/config` is unavailable. They are also merged
 * with the API response when it succeeds (mergeServiceConfig).
 */

import type { CalculableService } from '../types/calculator.types';

// ---------------------------------------------------------------------------
// Tax brackets & rates
// ---------------------------------------------------------------------------

export const IRPF_BRACKETS: readonly { min: number; max: number; rate: number }[] = [
  { min: 0, max: 1_000_000, rate: 0 },
  { min: 1_000_000, max: 3_000_000, rate: 10 },
  { min: 3_000_000, max: 5_000_000, rate: 15 },
  { min: 5_000_000, max: 10_000_000, rate: 20 },
  { min: 10_000_000, max: 15_000_000, rate: 25 },
  { min: 15_000_000, max: Number.POSITIVE_INFINITY, rate: 35 },
];

export const VAT_STANDARD_RATE = 15;
export const CORPORATE_TAX_RATE = 35;

// ---------------------------------------------------------------------------
// Default services — ids must match backend `fiscal_services.id`
// (same as web. If admin updates them in DB the API merge will override
// percentage / formula variables — see use-merged-services.ts.)
// ---------------------------------------------------------------------------

export const DEFAULT_CALCULABLE_SERVICES: CalculableService[] = [
  {
    id: 876,
    name_es: 'Reconocimiento y comprobación de calidad',
    name_fr: 'Reconnaissance et vérification de la qualité',
    name_en: 'Quality recognition and verification',
    type: 'percentage',
    percentage: 0.2,
  },
  {
    id: 877,
    name_es: 'Inspección técnica',
    name_fr: 'Inspection technique',
    name_en: 'Technical inspection',
    type: 'percentage',
    percentage: 0.2,
  },
  {
    id: 879,
    name_es: 'Buque de línea no regular',
    name_fr: 'Navire de ligne non régulier',
    name_en: 'Non-regular line vessel',
    type: 'percentage',
    percentage: 0.02,
  },
  {
    id: 871,
    name_es: 'Canon anual de concesiones',
    name_fr: 'Redevance annuelle de concessions',
    name_en: 'Annual concession fee',
    type: 'formula',
    formula: 'RF + (t * CA / 100)',
    formula_description_es: 'Cuota fija + (Tasa % × Facturación anual / 100)',
    formula_description_fr: "Redevance fixe + (Taux % × Chiffre d'affaires annuel / 100)",
    formula_description_en: 'Fixed fee + (Rate % × Annual turnover / 100)',
    variables: [
      {
        key: 'RF',
        type: 'currency',
        label_es: 'Cuota fija anual',
        label_fr: 'Redevance fixe annuelle',
        label_en: 'Annual fixed fee',
        description_es: 'Monto fijo anual en XAF',
        description_fr: 'Montant fixe annuel en XAF',
        description_en: 'Annual fixed amount in XAF',
        defaultValue: 0,
      },
      {
        key: 't',
        type: 'number',
        label_es: 'Tasa de la cuota (%)',
        label_fr: 'Taux de la redevance (%)',
        label_en: 'Fee rate (%)',
        description_es: 'Ej: 1 para 1%, 5 para 5%',
        description_fr: 'Ex: 1 pour 1%, 5 pour 5%',
        description_en: 'E.g., 1 for 1%, 5 for 5%',
        defaultValue: 1,
      },
      {
        key: 'CA',
        type: 'currency',
        label_es: 'Facturación anual',
        label_fr: "Chiffre d'affaires annuel",
        label_en: 'Annual turnover',
        description_es: 'Facturación anual declarada en XAF',
        description_fr: "Chiffre d'affaires annuel déclaré en XAF",
        description_en: 'Declared annual turnover in XAF',
        defaultValue: 0,
      },
    ],
  },
];
