/**
 * Calculator types — ported from web `calculateur/page.tsx`.
 *
 * Mobile keeps the same shape as web for parity. Field naming intentionally
 * mirrors the web's `name_es` / `label_es` conventions (the same multilingual
 * fields are also returned by the backend `GET /homepage/calculator/config`
 * via `name`).
 */

export type CalculatorTab = 'irpf' | 'vat' | 'corporate' | 'services';

export type VatMode = 'add' | 'extract';

export type CalculationMethod = 'percentage' | 'formula';

export interface PercentageService {
  id: number;
  name_es: string;
  name_fr: string;
  name_en: string;
  type: 'percentage';
  /** Percentage rate (e.g. 0.2 means 0.2%). */
  percentage: number;
}

export interface FormulaVariable {
  key: string;
  type: 'number' | 'currency';
  label_es: string;
  label_fr: string;
  label_en: string;
  description_es?: string;
  description_fr?: string;
  description_en?: string;
  defaultValue?: number;
}

export interface FormulaService {
  id: number;
  name_es: string;
  name_fr: string;
  name_en: string;
  type: 'formula';
  /** Arithmetic formula referencing variable keys (e.g. "RF + (t * CA / 100)"). */
  formula: string;
  formula_description_es: string;
  formula_description_fr: string;
  formula_description_en: string;
  variables: FormulaVariable[];
}

export type CalculableService = PercentageService | FormulaService;

// ---------------------------------------------------------------------------
// API response — `GET /api/v1/homepage/calculator/config?language={lng}`
// ---------------------------------------------------------------------------

export interface ApiCalculationConfigVariable {
  type: 'number' | 'currency';
  label_es?: string;
  label_fr?: string;
  label_en?: string;
  description_es?: string;
  description_fr?: string;
  description_en?: string;
  default_value?: number;
}

export interface ApiCalculationConfig {
  formula?: string;
  variables?: Record<string, ApiCalculationConfigVariable>;
}

export interface ApiServiceConfig {
  id: number;
  name: string;
  /** "percentage_based" | "formula_based" | other */
  calculation_method: string;
  base_percentage: number | null;
  expedition_formula: string | null;
  calculation_config: ApiCalculationConfig | null;
}

export interface CalculatorConfigResponse {
  services: ApiServiceConfig[];
  count: number;
}

// ---------------------------------------------------------------------------
// Calculation results
// ---------------------------------------------------------------------------

export interface IrpfBracketBreakdown {
  bracket: string;
  taxable: number;
  rate: number;
  tax: number;
}

export interface IrpfResult {
  grossAmount: number;
  taxAmount: number;
  netAmount: number;
  effectiveRate: number;
  breakdown: IrpfBracketBreakdown[];
}

export interface VatResult {
  baseAmount: number;
  vatAmount: number;
  totalAmount: number;
}

export interface CorporateResult {
  profit: number;
  tax: number;
  netProfit: number;
}

export interface ServiceCalculationBreakdownItem {
  label: string;
  value: string;
}

export interface ServiceCalculationResult {
  serviceName: string;
  result: number;
  formula: string;
  breakdown: ServiceCalculationBreakdownItem[];
}
