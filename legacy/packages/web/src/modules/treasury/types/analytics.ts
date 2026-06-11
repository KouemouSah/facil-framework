/**
 * Treasury Analytics Types
 * TypeScript types for statistical analysis
 *
 * @module treasury/types/analytics
 */

// =============================================================================
// ENUMS
// =============================================================================

export type CorrelationStrength = 'weak' | 'moderate' | 'strong';

export type TrendDirection = 'declining' | 'stable' | 'growing';

export type FindingSeverity = 'info' | 'warning' | 'critical';

export type FindingCategory =
  | 'correlation'
  | 'trend'
  | 'anomaly'
  | 'sla'
  | 'prediction'
  | 'performance';

export type HealthStatus = 'good' | 'warning' | 'critical';

// =============================================================================
// DESCRIPTIVE STATISTICS
// =============================================================================

export interface DescriptiveStats {
  metricName: string;
  count: number;
  mean: number;
  median: number;
  std: number;
  min: number;
  max: number;
  q1: number;
  q3: number;
  iqr: number;
}

export interface StatisticsResponse {
  period: string;
  dateFrom: string;
  dateTo: string;
  totalRecords: number;
  metrics: DescriptiveStats[];
}

// =============================================================================
// CORRELATIONS
// =============================================================================

export interface CorrelationResult {
  variable1: string;
  variable2: string;
  coefficient: number;
  pValue: number;
  strength: CorrelationStrength;
  isSignificant: boolean;
}

export interface CorrelationMatrix {
  period: string;
  dateFrom: string;
  dateTo: string;
  correlations: CorrelationResult[];
  variablesAnalyzed: string[];
}

// =============================================================================
// TREND ANALYSIS
// =============================================================================

export interface TrendAnalysis {
  metricName: string;
  slope: number;
  intercept: number;
  rSquared: number;
  direction: TrendDirection;
  slopePercentage: number;
  confidenceLevel: string;
  projection7d?: number;
  projection30d?: number;
  dataPoints: number;
  isReliable: boolean;
}

export interface TrendsResponse {
  period: string;
  dateFrom: string;
  dateTo: string;
  trends: TrendAnalysis[];
}

// =============================================================================
// ANOMALY DETECTION
// =============================================================================

export interface AnomalyPoint {
  date: string;
  metricName: string;
  value: number;
  expectedValue: number;
  zScore: number;
  deviationPercentage: number;
  anomalyType: 'high' | 'low';
}

export interface AnomaliesResponse {
  period: string;
  dateFrom: string;
  dateTo: string;
  totalAnomalies: number;
  anomalies: AnomalyPoint[];
  anomaliesByMetric: Record<string, number>;
}

// =============================================================================
// PREDICTIONS
// =============================================================================

export interface PredictionPoint {
  date: string;
  predictedValue: number;
  lowerBound: number;
  upperBound: number;
  confidenceLevel: number;
}

export interface PredictionsResponse {
  metricName: string;
  period: string;
  dateFrom: string;
  dateTo: string;
  horizonDays: number;
  modelType: string;
  rSquared: number;
  predictions: PredictionPoint[];
  warning?: string;
}

// =============================================================================
// REPORT FINDINGS
// =============================================================================

export interface ReportFinding {
  category: FindingCategory;
  severity: FindingSeverity;
  title: string;
  message: string;
  metricValue?: number;
  threshold?: number;
  recommendation?: string;
}

// =============================================================================
// COMPLETE ANALYTICS REPORT
// =============================================================================

export interface AnalyticsReport {
  period: string;
  dateFrom: string;
  dateTo: string;
  generatedAt: string;
  language: string;

  // Summary metrics
  totalRecords: number;
  totalAmount: number;
  totalTransactions: number;
  avgTransactionAmount: number;

  // Detailed analyses
  statistics: DescriptiveStats[];
  correlations: CorrelationResult[];
  trends: TrendAnalysis[];
  predictions: PredictionPoint[];
  anomalies: AnomalyPoint[];

  // Report section
  findings: ReportFinding[];
  alertsCount: number;
  warningsCount: number;

  // Overall health
  healthScore: number;
  healthStatus: HealthStatus;

  // Data quality
  dataDays: number;
  dataSufficient: boolean;

  // NL summaries
  trendSummary?: string;
  correlationSummary?: string;
}

// =============================================================================
// EXPLORE RESPONSE (for custom variable analysis)
// =============================================================================

export interface ExploreResponse {
  primaryVariable: string;
  secondaryVariable?: string;
  period: string;
  dateFrom?: string;
  dateTo?: string;
  statistics?: DescriptiveStats;
  trend?: TrendAnalysis;
  correlation?: CorrelationResult;
  anomalies: AnomalyPoint[];
  totalRecords: number;
  message?: string;
  dataDays?: number;
  summary?: string;
}

// =============================================================================
// REQUEST PARAMS
// =============================================================================

export interface AnalyticsParams {
  period?: string;
  dateFrom?: string;
  dateTo?: string;
}

export interface ReportParams extends AnalyticsParams {
  language?: string;
}

export interface PredictionParams extends AnalyticsParams {
  horizonDays?: number;
}

export interface ExploreParams extends AnalyticsParams {
  primaryVariable: string;
  secondaryVariable?: string;
}

// =============================================================================
// VARIABLE DEFINITIONS (for UI dropdowns)
// =============================================================================

export interface VariableDefinition {
  value: string;
  labelEs: string;
  labelFr: string;
  labelEn: string;
  category: 'financial' | 'operational' | 'quality';
  icon: string;
  supportsPredict: boolean;
  supportsTrend: boolean;
  supportsAnomaly: boolean;
}

export const ANALYTICS_VARIABLES: VariableDefinition[] = [
  {
    value: 'total_amount',
    labelEs: 'Ingresos (monto total)',
    labelFr: 'Revenus (montant total)',
    labelEn: 'Revenue (total amount)',
    category: 'financial',
    icon: 'DollarSign',
    supportsPredict: true,
    supportsTrend: true,
    supportsAnomaly: true,
  },
  {
    value: 'transaction_count',
    labelEs: 'Volumen (transacciones)',
    labelFr: 'Volume (transactions)',
    labelEn: 'Volume (transactions)',
    category: 'operational',
    icon: 'BarChart3',
    supportsPredict: true,
    supportsTrend: true,
    supportsAnomaly: true,
  },
  {
    value: 'avg_processing_minutes',
    labelEs: 'Tiempo de procesamiento',
    labelFr: 'Temps de traitement',
    labelEn: 'Processing time',
    category: 'operational',
    icon: 'Clock',
    supportsPredict: false,
    supportsTrend: true,
    supportsAnomaly: true,
  },
  {
    value: 'success_count',
    labelEs: 'Transacciones exitosas',
    labelFr: 'Transactions réussies',
    labelEn: 'Successful transactions',
    category: 'quality',
    icon: 'CheckCircle',
    supportsPredict: false,
    supportsTrend: true,
    supportsAnomaly: false,
  },
  {
    value: 'failed_count',
    labelEs: 'Transacciones fallidas',
    labelFr: 'Transactions échouées',
    labelEn: 'Failed transactions',
    category: 'quality',
    icon: 'XCircle',
    supportsPredict: false,
    supportsTrend: true,
    supportsAnomaly: false,
  },
];

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Get badge variant for correlation strength
 */
export function getCorrelationBadgeVariant(
  strength: CorrelationStrength
): 'default' | 'secondary' | 'destructive' {
  switch (strength) {
    case 'strong':
      return 'default';
    case 'moderate':
      return 'secondary';
    case 'weak':
      return 'destructive';
  }
}

/**
 * Get badge variant for trend direction
 */
export function getTrendBadgeVariant(
  direction: TrendDirection
): 'default' | 'secondary' | 'destructive' {
  switch (direction) {
    case 'growing':
      return 'default';
    case 'stable':
      return 'secondary';
    case 'declining':
      return 'destructive';
  }
}

/**
 * Get badge variant for finding severity
 */
export function getFindingBadgeVariant(
  severity: FindingSeverity
): 'default' | 'secondary' | 'destructive' {
  switch (severity) {
    case 'info':
      return 'secondary';
    case 'warning':
      return 'default';
    case 'critical':
      return 'destructive';
  }
}

/**
 * Get health status color class
 */
export function getHealthStatusColor(status: HealthStatus): string {
  switch (status) {
    case 'good':
      return 'text-green-600';
    case 'warning':
      return 'text-yellow-600';
    case 'critical':
      return 'text-red-600';
  }
}

/**
 * Format variable name for display
 */
export function formatVariableName(variable: string, locale: string): string {
  const def = ANALYTICS_VARIABLES.find((v) => v.value === variable);
  if (!def) return variable;

  switch (locale) {
    case 'fr':
      return def.labelFr;
    case 'en':
      return def.labelEn;
    default:
      return def.labelEs;
  }
}
