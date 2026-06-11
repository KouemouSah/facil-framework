/**
 * Treasury Module Types
 * Type definitions for Treasury Agent dashboard
 *
 * @module treasury/types
 */

// =============================================================================
// ENUMS (aligned with backend payment_workflow_status)
// =============================================================================

export type PaymentWorkflowStatus =
  | 'submitted'
  | 'auto_processing'
  | 'auto_approved'
  | 'pending_agent_review'
  | 'agent_reviewing'
  | 'requires_documents'
  | 'docs_resubmitted'
  | 'approved_by_agent'
  | 'rejected_by_agent'
  | 'escalated_supervisor'
  | 'supervisor_reviewing'
  | 'completed'
  | 'cancelled_by_user'
  | 'cancelled_by_agent'
  | 'expired';

export type PaymentStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed'
  | 'refunded'
  | 'cancelled';

export type PaymentMethod =
  | 'mobile_money'
  | 'card'
  | 'bank_transfer'
  | 'cash'
  | 'check';

export type BankCode =
  | 'BANGE'
  | 'BGFI'
  | 'CCEIBANK'
  | 'SGBGE'
  | 'ECOBANK';

export type TransactionStatus =
  | 'unreconciled'
  | 'reconciled'
  | 'failed';

// =============================================================================
// SERVICE PAYMENT (from service_payments table)
// =============================================================================

export interface TariffBreakdown {
  baseAmount: number;
  baseDescription?: string;
  supplements?: Array<{
    code: string;
    nameEs: string;
    unitPrice: number;
    quantity: number;
    subtotal: number;
  }>;
  supplementsTotal: number;
  penaltiesAmount: number;
  totalAmount: number;
  currency: string;
  tariffType?: string;
  workflowCode?: string;
}

export interface PendingPayment {
  id: string;
  paymentReference: string;
  serviceRequestId?: string;
  requestReference?: string;
  workflowCode?: string;
  userId: string;
  companyId?: string;
  paymentType?: string;
  baseAmount?: number;
  penalties?: number;
  discounts?: number;
  totalAmount: number;
  paymentMethod: PaymentMethod | string;
  currency: string;
  paymentStatus?: PaymentStatus;
  status?: PaymentStatus; // Alias for paymentStatus
  workflowStatus: PaymentWorkflowStatus | string;
  requiresAgentValidation?: boolean;
  slaTargetDate?: string;
  submittedAt?: string;
  createdAt: string;
  updatedAt?: string;
  hoursWaiting?: number;
  // Joined data
  userName?: string;
  userEmail?: string;
  userPhone?: string;
  beneficiaryName?: string;
  serviceName?: string;
  ministryName?: string;
  calculationDetails?: TariffBreakdown;
  // Computed fields from backend (extracted from calculationDetails)
  supplementsAmount?: number;
  supplements?: Array<{
    code: string;
    nameEs: string;
    unitPrice: number;
    quantity: number;
    subtotal: number;
  }>;
  // Reconciliation info
  bankTransactionId?: string;
  validatedAt?: string;
  // Assigned agent info (for supervisor view)
  assignedAgentId?: string;
  assignedAgentName?: string;
  // Site info
  locationName?: string;
  // Batch info (for batch payment grouping)
  batchId?: string;
  batchReference?: string;
  batchTotalItems?: number;
  // Escalation info
  escalationLevel?: string;
  escalationReason?: string;
  escalatedAt?: string;
  slaEscalated?: boolean;
  // Bundle-specific
  entityCode?: string;
  entityName?: string;
  companyName?: string;
  registrationNumber?: string;
  sectorActividad?: string;
  commerceType?: string;
  zoneCode?: string;
  zoneTier?: string;
  cityName?: string;
  obligationCount?: number;
  obligations?: Array<{ name: string; amount: number; fee_type: string }>;
}

export interface TreasuryAgentOption {
  id: string;
  name: string;
}

export interface PendingPaymentsListResponse {
  payments: PendingPayment[];
  total: number;
  page: number;
  pageSize: number;
  isSupervisor: boolean;
  isMainOffice: boolean;
  treasuryAgents?: TreasuryAgentOption[];
}

export interface PendingPaymentsParams {
  paymentMethod?: PaymentMethod | 'cash' | 'check';
  method?: string; // Alias for paymentMethod
  workflowStatus?: PaymentWorkflowStatus;
  status?: string; // Alias for workflowStatus
  page?: number;
  pageSize?: number;
  // Filter by assigned agent (supervisor only)
  agentProfileId?: string;
  // Filter by entity_location (site)
  entityLocationId?: string;
  // Date range filters (YYYY-MM-DD)
  dateFrom?: string;
  dateTo?: string;
}

// =============================================================================
// PAYMENT ACTIONS
// =============================================================================

export interface PaymentValidationRequest {
  comment?: string;
}

export interface PaymentRejectionRequest {
  reason: string;
}

export interface PaymentEscalationRequest {
  reason: string;
  level?: 'low' | 'medium' | 'high' | 'critical';
}

export interface BatchValidateResponse {
  success: boolean;
  paymentsValidated: number;
  batchReference?: string;
  error?: string;
}

export interface PaymentActionResponse {
  success: boolean;
  paymentId: string;
  newStatus?: PaymentWorkflowStatus;
  receiptNumber?: string;
  receiptUrl?: string;
  messageEs?: string;
  error?: string;
}

// =============================================================================
// ERROR TYPES (aligned with backend TreasuryError)
// =============================================================================

/**
 * Treasury error codes returned by the backend
 */
export enum TreasuryErrorCode {
  // Authentication & Authorization
  NO_AGENT_PROFILE = 'TREASURY_001',
  UNAUTHORIZED = 'TREASURY_002',
  INSUFFICIENT_PERMISSIONS = 'TREASURY_003',

  // Payment Errors
  PAYMENT_NOT_FOUND = 'TREASURY_100',

  // Validation Errors
  VALIDATION_FAILED = 'TREASURY_200',
  INVALID_PAYMENT_STATUS = 'TREASURY_201',
  ALREADY_VALIDATED = 'TREASURY_202',
  ALREADY_REJECTED = 'TREASURY_203',

  // Rejection Errors
  REJECTION_REASON_REQUIRED = 'TREASURY_300',

  // Reconciliation Errors
  TRANSACTION_NOT_FOUND = 'TREASURY_400',
  RECONCILIATION_FAILED = 'TREASURY_401',
  AMOUNT_MISMATCH = 'TREASURY_402',

  // Anomaly Errors
  ANOMALY_NOT_FOUND = 'TREASURY_500',
  ANOMALY_ALREADY_RESOLVED = 'TREASURY_501',
  COMMENT_REQUIRED = 'TREASURY_502',

  // Export Errors
  EXPORT_NOT_FOUND = 'TREASURY_600',
  EXPORT_NOT_READY = 'TREASURY_601',
  EXPORT_EXPIRED = 'TREASURY_602',

  // General Errors
  INVALID_DATE_RANGE = 'TREASURY_700',
  INTERNAL_ERROR = 'TREASURY_999',
}

/**
 * Structured error response from treasury endpoints
 */
export interface TreasuryErrorResponse {
  code: TreasuryErrorCode | string;
  message: string;
  info?: Record<string, unknown>;
}

/**
 * Parse API error to get user-friendly message
 */
export function getTreasuryErrorMessage(error: unknown): string {
  // Check if it's an Axios error with response data
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const axiosError = error as any;
  if (axiosError?.response?.data?.detail) {
    const detail = axiosError.response.data.detail;

    // Structured error from TreasuryError
    if (typeof detail === 'object' && detail.message) {
      return detail.message;
    }

    // Simple string error
    if (typeof detail === 'string') {
      return detail;
    }
  }

  // Check for generic error message
  if (axiosError?.message) {
    return axiosError.message;
  }

  // Default message
  return 'Ha ocurrido un error. Intente nuevamente.';
}

/**
 * Get error code from API error response
 */
export function getTreasuryErrorCode(error: unknown): TreasuryErrorCode | null {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const axiosError = error as any;
  if (axiosError?.response?.data?.detail?.code) {
    return axiosError.response.data.detail.code as TreasuryErrorCode;
  }
  return null;
}

// =============================================================================
// BANK TRANSACTIONS (from bank_transactions table)
// =============================================================================

export interface BankTransaction {
  id: string;
  bankCode: BankCode;
  bankReference: string;
  transactionId: string; // Alias for bankReference
  bankTransactionDate?: string;
  amount: number;
  currency: string;
  accountNumber?: string;
  accountHolderName?: string;
  senderName?: string; // Alias for accountHolderName
  senderPhone?: string;
  servicePaymentId?: string;
  status: TransactionStatus;
  reconciledAt?: string;
  reconciledBy?: string;
  rawData?: Record<string, unknown>;
  receivedAt: string; // Alias for createdAt
  createdAt: string;
  updatedAt?: string;
}

export interface BankTransactionListResponse {
  transactions: BankTransaction[];
  total: number;
  page: number;
  pageSize: number;
}

export interface BankTransactionParams {
  status?: TransactionStatus | 'all';
  bankCode?: BankCode;
  page?: number;
  pageSize?: number;
  search?: string;
}

export interface SearchPaymentResult {
  id: string;
  paymentReference: string;
  totalAmount: number;
  currency: string;
  paymentMethod: string;
  paymentDate: string | null;
  payerName: string;
  payerEmail: string;
}

export interface ReconcileRequest {
  bankTransactionId: string;
  servicePaymentId: string;
}

// =============================================================================
// BANK CONFIGURATIONS (from bank_configurations table)
// =============================================================================

export interface BankConfiguration {
  id: number;
  bankCode: BankCode | string;
  bankName: string;
  apiEndpoint?: string;
  apiUrl?: string; // Alias for apiEndpoint
  apiVersion?: string;
  webhookUrl?: string;
  treasuryAccountNumber: string;
  isActive: boolean;
  supportsWebhooks: boolean;
  supportsDirectIntegration: boolean;
  requiresManualValidation: boolean;
  gatewayType?: string | null;
  supportedPaymentMethods?: string[];
  isPrimary?: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface BankConfigurationCreate {
  bankCode: BankCode;
  bankName: string;
  apiEndpoint?: string;
  apiVersion?: string;
  apiKeyEncrypted?: string;
  webhookSecret?: string;
  treasuryAccountNumber: string;
  isActive?: boolean;
  supportsWebhooks?: boolean;
  supportsDirectIntegration?: boolean;
  gatewayType?: string | null;
  supportedPaymentMethods?: string[];
  isPrimary?: boolean;
}

export interface BankConfigurationUpdate {
  bankName?: string;
  apiEndpoint?: string;
  apiVersion?: string;
  apiKeyEncrypted?: string;
  webhookSecret?: string;
  treasuryAccountNumber?: string;
  isActive?: boolean;
  supportsWebhooks?: boolean;
  supportsDirectIntegration?: boolean;
  gatewayType?: string | null;
  supportedPaymentMethods?: string[];
  isPrimary?: boolean;
}

// =============================================================================
// TREASURY STATS (for dashboard)
// =============================================================================

export interface TreasuryStats {
  pendingValidationCount: number;
  unreconciledCount: number;
  todayValidatedCount: number;
  todayValidatedAmount: number;
  currency: string;
}

// =============================================================================
// PAYMENT METHOD CONFIGURATIONS (from payment_method_configurations table)
// =============================================================================

export type ProcessorType = 'gateway_api' | 'bange_api' | 'manual';

export interface PaymentMethodConfig {
  id: number;
  code: string;
  labelEs: string;
  // Note: Translations (FR/EN) are managed via entity_translations table
  processorType: ProcessorType;
  requiresPhone: boolean;
  requiresRedirect: boolean;
  requiresAgentValidation: boolean;
  isActive: boolean;
  displayOrder: number;
  icon: string;
  minAmount?: number;
  maxAmount?: number;
  feesPercentage: number;
  feesFixed: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface PaymentMethodConfigCreate {
  code: string;
  labelEs: string;
  // Note: Translations (FR/EN) are managed via entity_translations table
  processorType?: ProcessorType;
  requiresPhone?: boolean;
  requiresRedirect?: boolean;
  requiresAgentValidation?: boolean;
  isActive?: boolean;
  displayOrder?: number;
  icon?: string;
  minAmount?: number;
  maxAmount?: number;
  feesPercentage?: number;
  feesFixed?: number;
}

export interface PaymentMethodConfigUpdate {
  labelEs?: string;
  // Note: Translations (FR/EN) are managed via entity_translations table
  processorType?: ProcessorType;
  requiresPhone?: boolean;
  requiresRedirect?: boolean;
  requiresAgentValidation?: boolean;
  isActive?: boolean;
  displayOrder?: number;
  icon?: string;
  minAmount?: number;
  maxAmount?: number;
  feesPercentage?: number;
  feesFixed?: number;
}

export interface PaymentMethodReorderRequest {
  order: string[];
}

// =============================================================================
// AUDIT (Phase 1A)
// =============================================================================

export type AgentActionType =
  | 'approve'
  | 'reject'
  | 'request_documents'
  | 'escalate';

export interface AuditEntry {
  id: string;
  paymentId: string;
  paymentReference: string;
  serviceRequestId?: string;
  serviceRequestReference?: string;
  action: AgentActionType;
  fromStatus?: PaymentWorkflowStatus;
  toStatus?: PaymentWorkflowStatus;
  comment?: string;
  agentProfileId?: string;  // UUID from agent_profiles table
  agentName?: string;
  agentEmail?: string;
  actionDurationSeconds?: number;
  ipAddress?: string;
  createdAt: string;
}

export interface AuditListResponse {
  entries: AuditEntry[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AuditParams {
  paymentId?: string;
  agentProfileId?: string;  // UUID from agent_profiles table
  action?: AgentActionType;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface PaymentAuditDetail {
  paymentId: string;
  paymentReference: string;
  serviceRequestId?: string;
  serviceRequestReference?: string;
  workflowCode?: string;
  currentStatus: PaymentWorkflowStatus;
  createdAt: string;
  timeline: AuditEntry[];
  totalProcessingMinutes?: number;
}

// =============================================================================
// SLA STATS (Phase 1B)
// =============================================================================

export type SLAStatus = 'on_time' | 'warning' | 'critical' | 'breached';

export interface SLAStats {
  totalPending: number;
  onTime: number;
  warning: number;
  critical: number;
  breached: number;
  avgProcessingMinutes?: number;
  maxProcessingMinutes?: number;
  slaRespectRate: number;
  byPaymentMethod?: Record<string, {
    total: number;
    onTime: number;
    warning: number;
    critical: number;
    breached: number;
  }>;
}

/**
 * Calculate SLA status from target date
 */
export function calculateSLAStatus(
  slaTargetDate: string | undefined | null,
  workflowStatus: PaymentWorkflowStatus | string
): SLAStatus | 'completed' {
  // Completed statuses
  const completedStatuses: string[] = [
    'completed',
    'cancelled_by_user',
    'cancelled_by_agent',
    'expired',
  ];

  if (completedStatuses.includes(workflowStatus)) {
    return 'completed';
  }

  if (!slaTargetDate) {
    return 'on_time';
  }

  const now = new Date();
  const target = new Date(slaTargetDate);
  const diffMs = target.getTime() - now.getTime();
  const diffHours = diffMs / (1000 * 60 * 60);

  if (diffHours < 0) {
    return 'breached';
  } else if (diffHours < 2) {
    return 'critical';
  } else if (diffHours < 6) {
    return 'warning';
  }
  return 'on_time';
}

// =============================================================================
// ANOMALIES (Phase 2A)
// =============================================================================

export type AnomalyType =
  | 'duplicate_payment'
  | 'amount_mismatch'
  | 'reference_missing'
  | 'orphan_transaction'
  | 'late_validation'
  | 'suspicious_pattern'
  | 'high_amount'
  | 'other';

export type AnomalyStatus =
  | 'open'
  | 'investigating'
  | 'resolved'
  | 'false_positive'
  | 'escalated';

export type AnomalySeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Anomaly {
  id: string;
  entityType: string;
  entityId: string;
  paymentReference?: string;
  serviceRequestId?: string;
  serviceRequestReference?: string;
  anomalyType: AnomalyType;
  severity: AnomalySeverity;
  status: AnomalyStatus;
  title: string;
  description?: string;
  detectedBy: 'system' | 'agent';
  detectedAt: string;
  resolvedAt?: string;
  resolvedBy?: string;
  resolvedByName?: string;
  resolution?: string;
  affectedAmount?: number;
  relatedEntities?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  createdAt: string;
  updatedAt?: string;
}

export interface AnomalySummary {
  open: number;
  investigating: number;
  resolved: number;
  falsePositive: number;
  escalated: number;
  total: number;
}

export interface AnomalyListResponse {
  anomalies: Anomaly[];
  total: number;
  summary: AnomalySummary;
}

export interface AnomalyParams {
  status?: AnomalyStatus;
  severity?: AnomalySeverity;
  anomalyType?: AnomalyType;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface AnomalyCreateRequest {
  entityType: string;
  entityId: string;
  anomalyType: AnomalyType;
  severity: AnomalySeverity;
  title: string;
  description?: string;
  affectedAmount?: number;
  relatedEntities?: Record<string, unknown>;
}

export interface AnomalyStatusUpdateRequest {
  newStatus: AnomalyStatus;
  comment?: string;
  resolution?: string;
}

export interface AnomalyAction {
  id: string;
  anomalyId: string;
  action: string;
  fromStatus?: AnomalyStatus;
  toStatus?: AnomalyStatus;
  comment?: string;
  performedByName?: string;
  performedAt: string;
}

// =============================================================================
// EXPORTS (Phase 2B)
// =============================================================================

export type ExportType =
  | 'sage_x3'
  | 'ministry_report'
  | 'bank_central'
  | 'audit_report'
  | 'reconciliation'
  | 'custom';

export type ExportFormat = 'csv' | 'xlsx' | 'pdf' | 'xml' | 'json';

export type ExportStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface ExportFilters {
  entityCode?: string;
  paymentMethod?: string;
  workflowCode?: string;
  status?: string;
}

export interface TreasuryExport {
  id: string;
  exportType: ExportType;
  exportFormat: ExportFormat;
  periodStart: string;
  periodEnd: string;
  filters?: ExportFilters;
  status: ExportStatus;
  progressPercentage: number;
  totalRecords?: number;
  totalAmount?: number;
  currency: string;
  fileName?: string;
  fileSizeBytes?: number;
  errorMessage?: string;
  requestedByName?: string;
  requestedAt: string;
  startedAt?: string;
  completedAt?: string;
  downloadCount: number;
}

export interface ExportListResponse {
  exports: TreasuryExport[];
  total: number;
}

export interface ExportParams {
  status?: ExportStatus;
  exportType?: ExportType;
  periodStart?: string;
  periodEnd?: string;
  page?: number;
  pageSize?: number;
}

export interface ExportCreateRequest {
  exportType: ExportType;
  exportFormat: ExportFormat;
  periodStart: string;
  periodEnd: string;
  filters?: ExportFilters;
  templateCode?: string;
}

export interface ExportTemplate {
  id: number;
  code: string;
  name: string;
  exportType: ExportType;
  exportFormat: ExportFormat;
  description?: string;
  isActive: boolean;
}

export interface ExportDownloadResponse {
  blob: Blob;
  fileName: string;
}

// =============================================================================
// KPIs (Phase 4)
// =============================================================================

export type KPIPeriod = 'day' | 'week' | 'month' | 'year' | 'custom';

export interface KPIParams {
  period?: KPIPeriod;
  dateFrom?: string;
  dateTo?: string;
}

export interface PaymentMethodKPI {
  method: string;
  count: number;
  amount: number;
  percentage: number;
  successRate: number;
  avgProcessingMinutes?: number;
}

export interface EntityKPI {
  entityCode: string;
  entityName: string;
  count: number;
  amount: number;
  percentage: number;
}

/** @deprecated Use EntityKPI instead */
export type MinistryKPI = EntityKPI;

export interface DailyTrend {
  date: string;
  count: number;
  amount: number;
}

export interface PeriodComparison {
  totalCollectedChange: number;
  transactionsChange: number;
  trend: 'up' | 'down' | 'stable';
}

export interface KPIResponse {
  period: string;
  dateFrom: string;
  dateTo: string;
  totalCollected: number;
  totalTransactions: number;
  avgTransactionAmount: number;
  slaRespectRate: number;
  byPaymentMethod: PaymentMethodKPI[];
  byEntity: EntityKPI[];
  dailyTrend: DailyTrend[];
  previousPeriod?: PeriodComparison;
}

export interface AgentStats {
  agentProfileId: string;  // UUID from agent_profiles table
  agentName: string;
  agentEmail?: string;
  validationsCount: number;
  rejectionsCount: number;
  avgProcessingMinutes: number;
  slaRespectRate: number;
  currentWorkload: number;
}

export interface AgentPerformanceResponse {
  period: string;
  dateFrom: string;
  dateTo: string;
  agents: AgentStats[];
  totalValidations: number;
  totalRejections: number;
}

// ─── Supervisor Overview (Phase 3 - Pilotage Dashboard) ─────

export interface PaymentFlowPoint {
  date: string;
  count: number;
  amount: number;
}

export interface AgentLoadItem {
  agentProfileId: string;
  agentName: string;
  pending: number;
  inProgress: number;
  completedToday: number;
  capacityPct: number;
  status: string;
}

export interface SLAAlertItem {
  paymentId: string;
  paymentReference: string;
  amount: number;
  currency: string;
  paymentMethod: string;
  userName: string;
  requestReference: string;
  slaStatus: 'breached' | 'critical' | 'warning' | 'ok';
  hoursRemaining: number;
  createdAt: string | null;
}

export interface MethodDistributionItem {
  method: string;
  count: number;
  amount: number;
  percentage: number;
}

export interface TopServiceItem {
  workflowCode: string;
  serviceName: string;
  count: number;
  amount: number;
}

export interface RecentActivityItem {
  action: string;
  agentName: string;
  paymentReference: string;
  amount: number;
  currency: string;
  paymentMethod: string;
  comment: string | null;
  createdAt: string | null;
}

export interface SLAComplianceData {
  totalValidated: number;
  withinSla: number;
  slaBreached: number;
  compliancePct: number;
  avgHours: number;
  minHours: number;
  maxHours: number;
  currentlyPending: number;
}

export interface SupervisorOverviewResponse {
  paymentFlow: PaymentFlowPoint[];
  agentLoad: AgentLoadItem[];
  slaAlerts: SLAAlertItem[];
  slaAlertsCount: number;
  slaCompliance: SLAComplianceData;
  methodDistribution: MethodDistributionItem[];
  topServices: TopServiceItem[];
  recentActivity: RecentActivityItem[];
  periodDays: number;
  isMainOffice: boolean;
  generatedAt: string;
}

// ─── Phase 4: Treasury AI Analyst ────────────────────────────

export interface TableArtifact {
  type: 'table';
  title: string;
  headers: string[];
  rows: string[][];
  alignments?: ('left' | 'right' | 'center')[];
}

export interface KpiGridArtifact {
  type: 'kpi_grid';
  title: string;
  metrics: { label: string; value: string; changePct?: number | null }[];
}

export interface SummaryArtifact {
  type: 'summary';
  title: string;
  content: string;
  severity?: 'info' | 'warning' | 'critical';
}

export type ArtifactData = TableArtifact | KpiGridArtifact | SummaryArtifact;

export interface TreasuryAnalystResponse {
  answer: string;
  toolsUsed: string[];
  data: Record<string, unknown>;
  artifacts?: ArtifactData[];
}

export interface TreasuryBriefingResponse {
  briefing: string;
  priority: 'normal' | 'attention' | 'urgent';
  recommendations: string[];
  data?: Record<string, unknown>;
}

// ─── Phase 5: Reconciliation Matching ────────────────────────

export interface MatchCandidate {
  paymentId: string;
  paymentReference: string;
  paymentAmount: number;
  payerName: string;
  paymentMethod: string;
  paymentDate: string | null;
  score: number;
  reasons: string[];
}

export interface ReconciliationSuggestion {
  transactionId: string;
  bankReference: string;
  bankAmount: number;
  bankCurrency: string;
  bankDate: string;
  accountHolder: string | null;
  bankCode: string;
  candidates: MatchCandidate[];
  bestScore: number;
}

export interface ReconciliationSuggestionsResponse {
  suggestions: ReconciliationSuggestion[];
  count: number;
}

export interface AutoMatchResult {
  transactionId: string;
  bankReference: string;
  paymentId: string;
  paymentReference: string;
  score: number;
  reasons: string[];
}

export interface AutoMatchResponse {
  matched: AutoMatchResult[];
  matchedCount: number;
  skipped: { transactionId: string; bankReference: string; bestScore: number; reason: string }[];
  skippedCount: number;
  threshold: number;
}

// ─── Workload Dashboard (Carga de Trabajo) ────────────────────

export interface DailyVelocityPoint {
  date: string;
  agentName: string;
  approved: number;
  rejected: number;
}

export interface WorkloadAgentLoad {
  agentName: string;
  pending: number;
  inProgress: number;
  capacityMax: number;
  capacityPct: number;
  status: string;
  completedPeriod: number;
  avgHours: number;
}

export interface SLABreakdown {
  onTime: number;
  breached: number;
  noSla: number;
  compliancePct: number;
  avgResolutionHours: number;
}

export interface VolumeTrendPoint {
  date: string;
  incoming: number;
  outgoing: number;
}

export interface ProcessingTimeAgent {
  agentName: string;
  minHours: number;
  avgHours: number;
  maxHours: number;
  p50Hours: number;
  count: number;
}

export interface WorkloadKPIs {
  totalAgents: number;
  activeAgents: number;
  queueSize: number;
  avgQueueWaitHours: number;
  velocityPerDay: number;
  totalValidatedPeriod: number;
}

export interface AgentRanking {
  agentName: string;
  validated: number;
  rejected: number;
  avgMinutes: number;
  score: number;
}

export interface WorkloadDashboardResponse {
  dailyVelocity: DailyVelocityPoint[];
  agentLoad: WorkloadAgentLoad[];
  slaBreakdown: SLABreakdown;
  volumeTrend: VolumeTrendPoint[];
  processingTimes: ProcessingTimeAgent[];
  kpis: WorkloadKPIs;
  rankings: AgentRanking[];
  periodDays: number;
  generatedAt: string;
}
