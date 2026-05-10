'use client';

import { useState, useMemo, Suspense, useCallback, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { appConfig } from '@/core/config/app';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Calculator, Receipt, Building2, Info, ArrowRight, RefreshCw, Circle, FileText } from 'lucide-react';
import Breadcrumb from '@/components/ui/breadcrumb';
import { getLocalizedName, getLocalizedField } from '@/core/utils/i18n-helpers';

// ============================================================================
// CONFIGURATION - Services with calculated prices
// These are predefined based on the fiscal services database
// Values can be overridden from backend when columns are added
// ============================================================================

interface PercentageService {
  id: number;
  name_es: string;
  name_fr: string;
  name_en: string;
  type: 'percentage';
  percentage: number; // Percentage rate (e.g., 0.2 means 0.2%)
}

interface FormulaVariable {
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

interface FormulaService {
  id: number;
  name_es: string;
  name_fr: string;
  name_en: string;
  type: 'formula';
  formula: string; // e.g., "RF + (t * CA / 100)"
  formula_description_es: string;
  formula_description_fr: string;
  formula_description_en: string;
  variables: FormulaVariable[];
}

type CalculableService = PercentageService | FormulaService;

// API response interface for calculator config
interface ApiCalculationConfig {
  formula?: string;
  variables?: Record<string, {
    type: 'number' | 'currency';
    label_es?: string;
    label_fr?: string;
    label_en?: string;
    description_es?: string;
    description_fr?: string;
    description_en?: string;
    default_value?: number;
  }>;
}

interface ApiServiceConfig {
  id: number;
  name: string;
  calculation_method: string;
  base_percentage: number | null;
  expedition_formula: string | null;
  calculation_config: ApiCalculationConfig | null;
}

interface CalculatorConfigResponse {
  services: ApiServiceConfig[];
  count: number;
}

// Predefined services - based on fiscal_services table
// These are default values that can be overridden by API
const DEFAULT_CALCULABLE_SERVICES: CalculableService[] = [
  // Percentage-based services
  {
    id: 876,
    name_es: 'Reconocimiento y comprobación de calidad',
    name_fr: 'Reconnaissance et vérification de la qualité',
    name_en: 'Quality recognition and verification',
    type: 'percentage',
    percentage: 0.2, // 0.2% of declared value
  },
  {
    id: 877,
    name_es: 'Inspección técnica',
    name_fr: 'Inspection technique',
    name_en: 'Technical inspection',
    type: 'percentage',
    percentage: 0.2, // 0.2% of declared value
  },
  {
    id: 879,
    name_es: 'Buque de línea no regular',
    name_fr: 'Navire de ligne non régulier',
    name_en: 'Non-regular line vessel',
    type: 'percentage',
    percentage: 0.02, // 0.02% of declared value
  },
  // Formula-based services
  {
    id: 871,
    name_es: 'Canon anual de concesiones',
    name_fr: 'Redevance annuelle de concessions',
    name_en: 'Annual concession fee',
    type: 'formula',
    formula: 'RF + (t * CA / 100)', // t is percentage, divide by 100
    formula_description_es: 'Cuota fija + (Tasa % × Facturación anual / 100)',
    formula_description_fr: 'Redevance fixe + (Taux % × Chiffre d\'affaires annuel / 100)',
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
        label_fr: 'Chiffre d\'affaires annuel',
        label_en: 'Annual turnover',
        description_es: 'Facturación anual declarada en XAF',
        description_fr: 'Chiffre d\'affaires annuel déclaré en XAF',
        description_en: 'Declared annual turnover in XAF',
        defaultValue: 0,
      },
    ],
  },
];

// ============================================================================
// TAX BRACKETS AND RATES
// ============================================================================

const IRPF_BRACKETS = [
  { min: 0, max: 1000000, rate: 0 },
  { min: 1000000, max: 3000000, rate: 10 },
  { min: 3000000, max: 5000000, rate: 15 },
  { min: 5000000, max: 10000000, rate: 20 },
  { min: 10000000, max: 15000000, rate: 25 },
  { min: 15000000, max: Infinity, rate: 35 },
];

const VAT_STANDARD_RATE = 15;
const CORPORATE_TAX_RATE = 35;

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

function formatCurrencyValue(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value) + ' XAF';
}

function parseNumberInput(value: string): number {
  const cleaned = value.replace(/[^\d.-]/g, '');
  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? 0 : parsed;
}

// Safe formula evaluation using recursive descent parser (no eval)
function evaluateFormula(formula: string, variables: Record<string, number>): number | null {
  try {
    let evalFormula = formula;
    for (const [key, value] of Object.entries(variables)) {
      const regex = new RegExp(`\\b${key}\\b`, 'g');
      evalFormula = evalFormula.replace(regex, String(value));
    }

    // Only allow safe characters: digits, whitespace, operators, parentheses, decimal point
    const safePattern = /^[\d\s+\-*/().]+$/;
    if (!safePattern.test(evalFormula)) {
      return null;
    }

    const result = safeEval(evalFormula);
    return typeof result === 'number' && isFinite(result) ? result : null;
  } catch {
    return null;
  }
}

// Recursive descent parser for arithmetic expressions (replaces eval)
// Supports: +, -, *, /, parentheses, decimal numbers
function safeEval(expr: string): number {
  const matched = expr.match(/(\d+\.?\d*|[+\-*/()])/g);
  if (!matched) throw new Error('Invalid expression');
  const tokens: string[] = matched;
  let pos = 0;

  function peek(): string | undefined { return tokens[pos]; }
  function consume(): string { return tokens[pos++]; }

  function parseExpr(): number {
    let left = parseTerm();
    while (peek() === '+' || peek() === '-') {
      const op = consume();
      const right = parseTerm();
      left = op === '+' ? left + right : left - right;
    }
    return left;
  }

  function parseTerm(): number {
    let left = parseFactor();
    while (peek() === '*' || peek() === '/') {
      const op = consume();
      const right = parseFactor();
      if (op === '/' && right === 0) throw new Error('Division by zero');
      left = op === '*' ? left * right : left / right;
    }
    return left;
  }

  function parseFactor(): number {
    if (peek() === '(') {
      consume(); // (
      const val = parseExpr();
      if (peek() !== ')') throw new Error('Missing closing parenthesis');
      consume(); // )
      return val;
    }
    // Handle unary minus
    if (peek() === '-') {
      consume();
      return -parseFactor();
    }
    const token = consume();
    const num = parseFloat(token);
    if (isNaN(num)) throw new Error('Invalid number');
    return num;
  }

  const result = parseExpr();
  if (pos < tokens.length) throw new Error('Unexpected token');
  return result;
}

// ============================================================================
// TYPES
// ============================================================================

type CalculatorType = 'irpf' | 'vat' | 'corporate' | 'services';

interface CalculationResult {
  grossAmount: number;
  taxAmount: number;
  netAmount: number;
  effectiveRate: number;
  breakdown: { bracket: string; taxable: number; rate: number; tax: number }[];
}

interface ServiceCalculationResult {
  serviceName: string;
  result: number;
  formula: string;
  breakdown: { label: string; value: string }[];
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

// Helper function to merge API config with defaults
function mergeServiceConfig(
  defaultService: CalculableService,
  apiConfig: ApiServiceConfig | undefined
): CalculableService {
  if (!apiConfig) {
    return defaultService;
  }

  // For percentage-based, update percentage from base_percentage
  if (defaultService.type === 'percentage' && apiConfig.base_percentage !== null) {
    return {
      ...defaultService,
      percentage: apiConfig.base_percentage,
    };
  }

  // For formula-based, update variables from calculation_config but keep default formula
  // (default formula has /100 for percentage conversion which is more user-friendly)
  if (defaultService.type === 'formula') {
    const config = apiConfig.calculation_config;

    if (config?.variables) {
      const updatedVariables: FormulaVariable[] = Object.entries(config.variables).map(([key, v]) => ({
        key,
        type: v.type,
        label_es: v.label_es || key,
        label_fr: v.label_fr || key,
        label_en: v.label_en || key,
        description_es: v.description_es,
        description_fr: v.description_fr,
        description_en: v.description_en,
        defaultValue: v.default_value,
      }));

      return {
        ...defaultService,
        // Keep default formula with /100 for user-friendly percentage input
        variables: updatedVariables,
      };
    }
  }

  return defaultService;
}

function CalculateurPageContent() {
  const params = useParams();
  const locale = (params?.locale as string) || 'es';
  const t = useTranslations('calculatorPage');

  const [activeTab, setActiveTab] = useState<CalculatorType>('irpf');
  const [irpfAmount, setIrpfAmount] = useState<string>('');
  const [vatAmount, setVatAmount] = useState<string>('');
  const [vatType, setVatType] = useState<'add' | 'extract'>('add');
  const [corporateProfit, setCorporateProfit] = useState<string>('');

  // Fiscal services calculator state
  const [selectedServiceId, setSelectedServiceId] = useState<number | null>(null);
  const [serviceInputs, setServiceInputs] = useState<Record<string, string>>({});
  const [calculationTriggered, setCalculationTriggered] = useState(false);

  // Services with merged configs from API
  const [calculableServices, setCalculableServices] = useState<CalculableService[]>(DEFAULT_CALCULABLE_SERVICES);

  // Load calculator config from API (runs once on mount)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await fetch(
          `${appConfig.api.baseUrl}/api/${appConfig.api.version}/homepage/calculator/config?language=${locale}`
        );

        if (response.ok) {
          const data: CalculatorConfigResponse = await response.json();

          // Merge API configs with defaults
          const mergedServices = DEFAULT_CALCULABLE_SERVICES.map(defaultService => {
            const apiConfig = data.services.find(s => s.id === defaultService.id);
            return mergeServiceConfig(defaultService, apiConfig);
          });

          setCalculableServices(mergedServices);
        }
      } catch (error) {
        console.error('Failed to load calculator config:', error);
        // Keep using defaults on error
      }
    };

    loadConfig();
  }, [locale]);

  // Get selected service
  const selectedService = useMemo(() => {
    return calculableServices.find(s => s.id === selectedServiceId) || null;
  }, [selectedServiceId, calculableServices]);

  // Get localized service name
  const getServiceName = useCallback((service: CalculableService): string => {
    return getLocalizedName(service as unknown as Record<string, unknown>, locale);
  }, [locale]);

  // Get localized variable label
  const getVariableLabel = useCallback((variable: FormulaVariable): string => {
    return getLocalizedField(variable as unknown as Record<string, unknown>, 'label', locale);
  }, [locale]);

  // Get localized variable description
  const getVariableDescription = useCallback((variable: FormulaVariable): string | undefined => {
    const desc = getLocalizedField(variable as unknown as Record<string, unknown>, 'description', locale);
    return desc || undefined;
  }, [locale]);

  // Get localized formula description
  const getFormulaDescription = useCallback((service: FormulaService): string => {
    if (locale === 'fr') return service.formula_description_fr;
    if (locale === 'en') return service.formula_description_en;
    return service.formula_description_es;
  }, [locale]);

  // Format functions
  const formatCurrency = useCallback((value: number): string => {
    return formatCurrencyValue(value, locale);
  }, [locale]);

  const formatPercent = useCallback((value: number): string => {
    return new Intl.NumberFormat(locale, {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 2,
    }).format(value / 100);
  }, [locale]);

  // IRPF Calculation
  const irpfResult = useMemo((): CalculationResult | null => {
    const amount = parseNumberInput(irpfAmount);
    if (amount <= 0) return null;

    let taxableRemaining = amount;
    let totalTax = 0;
    const breakdown: CalculationResult['breakdown'] = [];

    for (const bracket of IRPF_BRACKETS) {
      if (taxableRemaining <= 0) break;
      if (amount <= bracket.min) continue;

      const amountInBracket = Math.min(
        amount - bracket.min,
        bracket.max === Infinity ? amount - bracket.min : bracket.max - bracket.min
      );

      const actualAmount = Math.min(amountInBracket, taxableRemaining);
      if (actualAmount > 0 && bracket.rate > 0) {
        const tax = (actualAmount * bracket.rate) / 100;
        totalTax += tax;
        breakdown.push({
          bracket: bracket.max === Infinity
            ? `> ${formatCurrency(bracket.min)}`
            : `${formatCurrency(bracket.min)} - ${formatCurrency(bracket.max)}`,
          taxable: actualAmount,
          rate: bracket.rate,
          tax,
        });
        taxableRemaining -= actualAmount;
      } else if (bracket.rate === 0) {
        taxableRemaining -= amountInBracket;
      }
    }

    return {
      grossAmount: amount,
      taxAmount: totalTax,
      netAmount: amount - totalTax,
      effectiveRate: (totalTax / amount) * 100,
      breakdown,
    };
  }, [irpfAmount, formatCurrency]);

  // VAT Calculation
  const vatResult = useMemo(() => {
    const amount = parseNumberInput(vatAmount);
    if (amount <= 0) return null;

    if (vatType === 'add') {
      const vat = (amount * VAT_STANDARD_RATE) / 100;
      return { baseAmount: amount, vatAmount: vat, totalAmount: amount + vat };
    } else {
      const baseAmount = amount / (1 + VAT_STANDARD_RATE / 100);
      const vat = amount - baseAmount;
      return { baseAmount, vatAmount: vat, totalAmount: amount };
    }
  }, [vatAmount, vatType]);

  // Corporate Tax Calculation
  const corporateResult = useMemo(() => {
    const profit = parseNumberInput(corporateProfit);
    if (profit <= 0) return null;

    const tax = (profit * CORPORATE_TAX_RATE) / 100;
    return { profit, tax, netProfit: profit - tax };
  }, [corporateProfit]);

  // Fiscal Service Calculation
  const serviceResult = useMemo((): ServiceCalculationResult | null => {
    if (!selectedService || !calculationTriggered) return null;

    if (selectedService.type === 'percentage') {
      const baseAmount = parseNumberInput(serviceInputs['baseAmount'] || '0');
      if (baseAmount <= 0) return null;

      const result = (baseAmount * selectedService.percentage) / 100;

      return {
        serviceName: getServiceName(selectedService),
        result,
        formula: `${selectedService.percentage}% × ${formatCurrency(baseAmount)}`,
        breakdown: [
          { label: t('baseAmount'), value: formatCurrency(baseAmount) },
          { label: t('percentageRate'), value: `${selectedService.percentage}%` },
        ],
      };
    }

    if (selectedService.type === 'formula') {
      const variables: Record<string, number> = {};
      const breakdown: { label: string; value: string }[] = [];

      for (const variable of selectedService.variables) {
        const inputValue = serviceInputs[variable.key];
        const numValue = parseNumberInput(inputValue || String(variable.defaultValue || 0));
        variables[variable.key] = numValue;

        breakdown.push({
          label: getVariableLabel(variable),
          value: variable.type === 'currency' ? formatCurrency(numValue) : String(numValue),
        });
      }

      const result = evaluateFormula(selectedService.formula, variables);
      if (result === null) return null;

      return {
        serviceName: getServiceName(selectedService),
        result,
        formula: getFormulaDescription(selectedService),
        breakdown,
      };
    }

    return null;
  }, [selectedService, serviceInputs, calculationTriggered, getServiceName, getVariableLabel, getFormulaDescription, formatCurrency, t]);

  // Handlers
  const handleServiceChange = (value: string) => {
    const id = parseInt(value, 10);
    setSelectedServiceId(id);
    setServiceInputs({});
    setCalculationTriggered(false);
  };

  const handleInputChange = (key: string, value: string) => {
    setServiceInputs(prev => ({ ...prev, [key]: value }));
    setCalculationTriggered(false);
  };

  const handleCalculate = () => {
    setCalculationTriggered(true);
  };

  const handleReset = () => {
    setIrpfAmount('');
    setVatAmount('');
    setCorporateProfit('');
    setServiceInputs({});
    setCalculationTriggered(false);
  };

  // Render percentage-based form
  const renderPercentageForm = (service: PercentageService) => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="baseAmount">{t('baseAmountForPercentage')}</Label>
        <div className="relative">
          <Input
            id="baseAmount"
            type="text"
            placeholder="1,000,000"
            value={serviceInputs['baseAmount'] || ''}
            onChange={(e) => handleInputChange('baseAmount', e.target.value)}
            className="pr-16"
          />
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
            XAF
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {t('percentageRate')}: {service.percentage}%
        </p>
      </div>
    </div>
  );

  // Render formula-based form
  const renderFormulaForm = (service: FormulaService) => (
    <div className="space-y-4">
      {service.variables.map((variable) => (
        <div key={variable.key} className="space-y-2">
          <Label htmlFor={variable.key}>{getVariableLabel(variable)}</Label>
          <div className="relative">
            <Input
              id={variable.key}
              type="text"
              placeholder={variable.defaultValue?.toString() || '0'}
              value={serviceInputs[variable.key] || ''}
              onChange={(e) => handleInputChange(variable.key, e.target.value)}
              className={variable.type === 'currency' ? 'pr-16' : ''}
            />
            {variable.type === 'currency' && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">
                XAF
              </span>
            )}
          </div>
          {getVariableDescription(variable) && (
            <p className="text-xs text-muted-foreground">{getVariableDescription(variable)}</p>
          )}
        </div>
      ))}

      <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg">
        <p className="font-medium mb-1">{t('formula')}:</p>
        <p>{getFormulaDescription(service)}</p>
      </div>
    </div>
  );

  return (
    <div className="container mx-auto px-4 py-12">
      <Breadcrumb items={[{ label: t('title') }]} className="mb-6" />

      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-4">{t('title')}</h1>
        <p className="text-lg text-muted-foreground">{t('description')}</p>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as CalculatorType)} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-[650px]">
          <TabsTrigger value="irpf" className="gap-2">
            <Calculator className="h-4 w-4" />
            <span className="hidden sm:inline">{t('incomeTax')}</span>
            <span className="sm:hidden">IRPF</span>
          </TabsTrigger>
          <TabsTrigger value="vat" className="gap-2">
            <Receipt className="h-4 w-4" />
            <span>{t('vat')}</span>
          </TabsTrigger>
          <TabsTrigger value="corporate" className="gap-2">
            <Building2 className="h-4 w-4" />
            <span className="hidden sm:inline">{t('corporateTax')}</span>
            <span className="sm:hidden">IS</span>
          </TabsTrigger>
          <TabsTrigger value="services" className="gap-2">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">{t('fiscalServices')}</span>
            <span className="sm:hidden">{t('services')}</span>
          </TabsTrigger>
        </TabsList>

        {/* IRPF Calculator */}
        <TabsContent value="irpf">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calculator className="h-5 w-5 text-primary" />
                  {t('incomeTax')}
                </CardTitle>
                <CardDescription>{t('incomeTaxDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="irpf-amount">{t('annualIncome')}</Label>
                  <div className="relative">
                    <Input
                      id="irpf-amount"
                      type="text"
                      placeholder="5,000,000"
                      value={irpfAmount}
                      onChange={(e) => setIrpfAmount(e.target.value)}
                      className="pr-16"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">XAF</span>
                  </div>
                </div>

                <Button onClick={handleReset} variant="outline" size="sm" className="gap-2">
                  <RefreshCw className="h-4 w-4" />
                  {t('reset')}
                </Button>

                <Separator />

                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Info className="h-4 w-4 text-primary" />
                    {t('taxBrackets')}
                  </div>
                  <div className="space-y-1 bg-muted/30 p-4 rounded-lg border">
                    {[
                      { range: `${formatCurrency(0)} - ${formatCurrency(1000000)}`, rate: '0%', color: 'emerald' },
                      { range: `${formatCurrency(1000000)} - ${formatCurrency(3000000)}`, rate: '10%', color: 'green' },
                      { range: `${formatCurrency(3000000)} - ${formatCurrency(5000000)}`, rate: '15%', color: 'lime' },
                      { range: `${formatCurrency(5000000)} - ${formatCurrency(10000000)}`, rate: '20%', color: 'yellow' },
                      { range: `${formatCurrency(10000000)} - ${formatCurrency(15000000)}`, rate: '25%', color: 'orange' },
                      { range: `> ${formatCurrency(15000000)}`, rate: '35%', color: 'red' },
                    ].map((bracket, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-2 rounded hover:bg-background/50">
                        <Circle className={`h-3 w-3 fill-${bracket.color}-500 text-${bracket.color}-500`} />
                        <span className="flex-1 text-xs">{bracket.range}</span>
                        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold bg-${bracket.color}-100 text-${bracket.color}-800 dark:bg-${bracket.color}-900/30 dark:text-${bracket.color}-400`}>
                          {bracket.rate}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className={irpfResult ? 'border-primary/50' : ''}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ArrowRight className="h-5 w-5 text-primary" />
                  {t('result')}
                </CardTitle>
                <CardDescription>{t('calculationBreakdown')}</CardDescription>
              </CardHeader>
              <CardContent>
                {irpfResult ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-muted/50 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('grossIncome')}</p>
                        <p className="text-xl font-bold">{formatCurrency(irpfResult.grossAmount)}</p>
                      </div>
                      <div className="bg-destructive/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('totalTax')}</p>
                        <p className="text-xl font-bold text-destructive">{formatCurrency(irpfResult.taxAmount)}</p>
                      </div>
                      <div className="bg-green-500/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('netIncome')}</p>
                        <p className="text-xl font-bold text-green-600">{formatCurrency(irpfResult.netAmount)}</p>
                      </div>
                      <div className="bg-primary/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('effectiveRate')}</p>
                        <p className="text-xl font-bold text-primary">{formatPercent(irpfResult.effectiveRate)}</p>
                      </div>
                    </div>

                    <Separator />

                    <div className="space-y-2">
                      <p className="text-sm font-medium">{t('breakdownByBracket')}</p>
                      {irpfResult.breakdown.map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between text-sm bg-muted/30 p-2 rounded">
                          <div>
                            <span className="font-medium">{item.bracket}</span>
                            <span className="text-muted-foreground ml-2">@ {item.rate}%</span>
                          </div>
                          <span className="font-mono">{formatCurrency(item.tax)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Calculator className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>{t('enterAmount')}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* VAT Calculator */}
        <TabsContent value="vat">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Receipt className="h-5 w-5 text-primary" />
                  {t('vat')} ({VAT_STANDARD_RATE}%)
                </CardTitle>
                <CardDescription>{t('vatDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('calculationType')}</Label>
                  <div className="flex gap-2">
                    <Button variant={vatType === 'add' ? 'default' : 'outline'} size="sm" onClick={() => setVatType('add')} className="flex-1">
                      {t('addVat')}
                    </Button>
                    <Button variant={vatType === 'extract' ? 'default' : 'outline'} size="sm" onClick={() => setVatType('extract')} className="flex-1">
                      {t('extractVat')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="vat-amount">{vatType === 'add' ? t('baseAmount') : t('totalWithVat')}</Label>
                  <div className="relative">
                    <Input id="vat-amount" type="text" placeholder="1,000,000" value={vatAmount} onChange={(e) => setVatAmount(e.target.value)} className="pr-16" />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">XAF</span>
                  </div>
                </div>

                <Button onClick={handleReset} variant="outline" size="sm" className="gap-2">
                  <RefreshCw className="h-4 w-4" />
                  {t('reset')}
                </Button>

                <Separator />

                <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg">
                  <p className="font-medium mb-1">{t('formula')}:</p>
                  <p>{vatType === 'add' ? t('vatAddFormula') : t('vatExtractFormula')}</p>
                </div>
              </CardContent>
            </Card>

            <Card className={vatResult ? 'border-primary/50' : ''}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ArrowRight className="h-5 w-5 text-primary" />
                  {t('result')}
                </CardTitle>
                <CardDescription>{t('vatBreakdown')}</CardDescription>
              </CardHeader>
              <CardContent>
                {vatResult ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-4">
                      <div className="bg-muted/50 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('baseAmount')}</p>
                        <p className="text-xl font-bold">{formatCurrency(vatResult.baseAmount)}</p>
                      </div>
                      <div className="bg-amber-500/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('vatAmount')} ({VAT_STANDARD_RATE}%)</p>
                        <p className="text-xl font-bold text-amber-600">{formatCurrency(vatResult.vatAmount)}</p>
                      </div>
                      <div className="bg-primary/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('totalWithVat')}</p>
                        <p className="text-xl font-bold text-primary">{formatCurrency(vatResult.totalAmount)}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Receipt className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>{t('enterAmount')}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Corporate Tax Calculator */}
        <TabsContent value="corporate">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-primary" />
                  {t('corporateTax')} ({CORPORATE_TAX_RATE}%)
                </CardTitle>
                <CardDescription>{t('corporateTaxDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="corporate-profit">{t('taxableProfit')}</Label>
                  <div className="relative">
                    <Input id="corporate-profit" type="text" placeholder="10,000,000" value={corporateProfit} onChange={(e) => setCorporateProfit(e.target.value)} className="pr-16" />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground text-sm">XAF</span>
                  </div>
                </div>

                <Button onClick={handleReset} variant="outline" size="sm" className="gap-2">
                  <RefreshCw className="h-4 w-4" />
                  {t('reset')}
                </Button>

                <Separator />

                <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-lg">
                  <p className="font-medium mb-1">{t('formula')}:</p>
                  <p>{t('corporateFormula')}</p>
                </div>
              </CardContent>
            </Card>

            <Card className={corporateResult ? 'border-primary/50' : ''}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ArrowRight className="h-5 w-5 text-primary" />
                  {t('result')}
                </CardTitle>
                <CardDescription>{t('corporateBreakdown')}</CardDescription>
              </CardHeader>
              <CardContent>
                {corporateResult ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 gap-4">
                      <div className="bg-muted/50 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('taxableProfit')}</p>
                        <p className="text-xl font-bold">{formatCurrency(corporateResult.profit)}</p>
                      </div>
                      <div className="bg-destructive/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('corporateTaxAmount')} ({CORPORATE_TAX_RATE}%)</p>
                        <p className="text-xl font-bold text-destructive">{formatCurrency(corporateResult.tax)}</p>
                      </div>
                      <div className="bg-green-500/10 p-4 rounded-lg">
                        <p className="text-sm text-muted-foreground">{t('netProfit')}</p>
                        <p className="text-xl font-bold text-green-600">{formatCurrency(corporateResult.netProfit)}</p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Building2 className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>{t('enterAmount')}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Fiscal Services Calculator */}
        <TabsContent value="services">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-primary" />
                  {t('fiscalServices')}
                </CardTitle>
                <CardDescription>{t('fiscalServicesDesc')}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('selectService')}</Label>
                  <Select
                    value={selectedServiceId?.toString() || ''}
                    onValueChange={handleServiceChange}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('selectServicePlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      {calculableServices.map(service => (
                        <SelectItem key={service.id} value={service.id.toString()}>
                          {getServiceName(service)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {t('servicesCount', { count: calculableServices.length })}
                  </p>
                </div>

                {selectedService && (
                  <>
                    <Separator />

                    {selectedService.type === 'percentage' && renderPercentageForm(selectedService)}
                    {selectedService.type === 'formula' && renderFormulaForm(selectedService)}

                    <div className="flex gap-2 pt-2">
                      <Button onClick={handleCalculate} className="flex-1 gap-2">
                        <Calculator className="h-4 w-4" />
                        {t('calculate')}
                      </Button>
                      <Button onClick={handleReset} variant="outline" size="icon">
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                    </div>
                  </>
                )}

                {!selectedService && (
                  <div className="text-center py-8 text-muted-foreground">
                    <FileText className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>{t('selectServicePrompt')}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className={serviceResult ? 'border-primary/50' : ''}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ArrowRight className="h-5 w-5 text-primary" />
                  {t('result')}
                </CardTitle>
                <CardDescription>
                  {serviceResult ? serviceResult.serviceName : t('serviceCalculationResult')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {serviceResult ? (
                  <div className="space-y-4">
                    <div className="bg-primary/10 p-6 rounded-lg text-center">
                      <p className="text-sm text-muted-foreground mb-2">{t('calculatedAmount')}</p>
                      <p className="text-3xl font-bold text-primary">{formatCurrency(serviceResult.result)}</p>
                    </div>

                    <Separator />

                    <div className="space-y-2">
                      <p className="text-sm font-medium">{t('calculationBreakdown')}</p>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between text-sm bg-muted/30 p-2 rounded">
                          <span className="font-medium">{t('formula')}</span>
                          <span className="font-mono text-xs">{serviceResult.formula}</span>
                        </div>
                        {serviceResult.breakdown.map((item, idx) => (
                          <div key={idx} className="flex items-center justify-between text-sm bg-muted/30 p-2 rounded">
                            <span className="font-medium">{item.label}</span>
                            <span className="font-mono">{item.value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <Calculator className="h-12 w-12 mx-auto mb-3 opacity-30" />
                    <p>{selectedService ? t('enterVariables') : t('selectServiceFirst')}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Disclaimer */}
      <div className="mt-8 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
        <p className="text-sm text-amber-700 dark:text-amber-400 text-center">
          <Info className="h-4 w-4 inline mr-2" />
          {t('disclaimer')}
        </p>
      </div>
    </div>
  );
}

function CalculateurLoading() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl animate-pulse">
      <div className="h-6 bg-muted rounded w-48 mb-4" />
      <div className="h-10 bg-muted rounded w-64 mb-2" />
      <div className="h-4 bg-muted rounded w-96 mb-8" />
      <div className="h-12 bg-muted rounded mb-6" />
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="h-96 bg-muted rounded" />
        <div className="h-96 bg-muted rounded" />
      </div>
    </div>
  );
}

export default function CalculateurPage() {
  return (
    <Suspense fallback={<CalculateurLoading />}>
      <CalculateurPageContent />
    </Suspense>
  );
}
