/**
 * Treasury API Service
 * API calls for Treasury Agent dashboard
 *
 * @module treasury/services
 *
 * BACKEND ALIGNMENT:
 * Treasury Routes: /api/v1/admin/service-requests/treasury/*
 * Webhook Routes: /api/v1/webhooks/*
 */

import apiClient from '@/core/api/client';
import type {
  PendingPayment,
  PendingPaymentsListResponse,
  PendingPaymentsParams,
  PaymentValidationRequest,
  PaymentRejectionRequest,
  PaymentActionResponse,
  BankTransaction,
  BankTransactionListResponse,
  BankTransactionParams,
  ReconcileRequest,
  BankConfiguration,
  BankConfigurationCreate,
  BankConfigurationUpdate,
  TreasuryStats,
  PaymentMethodConfig,
  PaymentMethodConfigCreate,
  PaymentMethodConfigUpdate,
  PaymentMethodReorderRequest,
  // Phase 1A - Audit
  AuditEntry,
  AuditListResponse,
  AuditParams,
  PaymentAuditDetail,
  // Phase 1B - SLA
  SLAStats,
  // Phase 2A - Anomalies
  Anomaly,
  AnomalyListResponse,
  AnomalyParams,
  AnomalyCreateRequest,
  AnomalyStatusUpdateRequest,
  AnomalyAction,
  // Phase 2B - Exports
  TreasuryExport,
  ExportListResponse,
  ExportParams,
  ExportCreateRequest,
  ExportTemplate,
  ExportDownloadResponse,
  // Phase 4 - KPIs
  KPIResponse,
  PaymentMethodKPI,
  EntityKPI,
  DailyTrend,
  PeriodComparison,
  AgentPerformanceResponse,
  AgentStats,
  // Phase 3 - Supervisor Overview
  SupervisorOverviewResponse,
  // Phase 4 - AI Analyst
  TreasuryAnalystResponse,
  TreasuryBriefingResponse,
  ArtifactData,
  // Phase 5 - Reconciliation
  ReconciliationSuggestionsResponse,
  AutoMatchResponse,
  SearchPaymentResult,
  // Workload Dashboard
  WorkloadDashboardResponse,
} from '../types';
import type {
  // Phase 5 - Analytics
  StatisticsResponse,
  CorrelationMatrix,
  TrendsResponse,
  AnomaliesResponse,
  PredictionsResponse,
  AnalyticsReport,
  ExploreResponse,
  AnalyticsParams,
  ReportParams,
  PredictionParams,
  ExploreParams,
} from '../types/analytics';

// =============================================================================
// CONFIGURATION
// =============================================================================

const TREASURY_BASE = '/admin/service-requests/treasury';
const WEBHOOKS_BASE = '/webhooks';

// =============================================================================
// HELPERS
// =============================================================================

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
}

function toCamelCase<T>(obj: Record<string, unknown>): T {
  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const camelKey = snakeToCamel(key);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      result[camelKey] = toCamelCase(value as Record<string, unknown>);
    } else if (Array.isArray(value)) {
      result[camelKey] = value.map((item) => {
        // Preserve nested arrays as-is (e.g. rows: string[][] in table artifacts)
        if (Array.isArray(item)) return item;
        return typeof item === 'object' && item !== null
          ? toCamelCase(item as Record<string, unknown>)
          : item;
      });
    } else {
      result[camelKey] = value;
    }
  }
  return result as T;
}

function transformPayment(data: Record<string, unknown>): PendingPayment {
  const transformed = toCamelCase<PendingPayment & { paymentId?: string }>(data);
  // Backend returns payment_id -> paymentId, but PendingPayment interface expects id
  if (transformed.paymentId && !transformed.id) {
    transformed.id = transformed.paymentId;
  }
  return transformed as PendingPayment;
}

function transformTransaction(data: Record<string, unknown>): BankTransaction {
  return toCamelCase<BankTransaction>(data);
}

function transformBankConfig(data: Record<string, unknown>): BankConfiguration {
  return toCamelCase<BankConfiguration>(data);
}

// =============================================================================
// TREASURY PAYMENTS API
// =============================================================================

export const treasuryApi = {
  // -------------------------------------------------------------------------
  // Pending Payments
  // -------------------------------------------------------------------------

  /**
   * Get pending payments for validation
   * BACKEND: GET /api/v1/admin/service-requests/treasury/payments/pending
   */
  getPendingPayments: async (
    params: PendingPaymentsParams = {}
  ): Promise<PendingPaymentsListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      limit: params.pageSize || 20,
    };

    // Support both canonical names and aliases
    const paymentMethod = params.paymentMethod || params.method;
    const workflowStatus = params.workflowStatus || params.status;

    if (paymentMethod) {
      queryParams.payment_method = paymentMethod;
    }
    if (workflowStatus) {
      queryParams.workflow_status = workflowStatus;
    }
    // Filter by assigned agent (supervisor only)
    if (params.agentProfileId) {
      queryParams.agent_profile_id = params.agentProfileId;
    }
    // Filter by entity_location (site)
    if (params.entityLocationId) {
      queryParams.entity_location_id = params.entityLocationId;
    }
    // Date range filters
    if (params.dateFrom) {
      queryParams.date_from = params.dateFrom;
    }
    if (params.dateTo) {
      queryParams.date_to = params.dateTo;
    }

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/pending`,
      { params: queryParams }
    );

    const data = response.data;
    const payments = (data.payments as Record<string, unknown>[]) || [];
    return {
      payments: payments.map(transformPayment),
      total: (data.total as number) || 0,
      page: (data.page as number) || 1,
      pageSize: (data.page_size as number) || 20,
      isSupervisor: (data.is_supervisor as boolean) || false,
      isMainOffice: (data.is_main_office as boolean) || false,
      treasuryAgents: (data.treasury_agents as Array<{ id: string; name: string }>) || undefined,
    };
  },

  /**
   * Get single payment details
   */
  getPaymentDetails: async (paymentId: string): Promise<PendingPayment> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}`
    );
    return transformPayment(response.data);
  },

  // -------------------------------------------------------------------------
  // Payment Actions (Simplified: No lock/unlock with auto-assignment)
  // -------------------------------------------------------------------------

  /**
   * Validate (approve) payment
   * BACKEND: POST /api/v1/admin/service-requests/treasury/payments/{id}/validate
   */
  validatePayment: async (
    paymentId: string,
    request: PaymentValidationRequest = {}
  ): Promise<PaymentActionResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}/validate`,
      { comment: request.comment }
    );
    return toCamelCase<PaymentActionResponse>(response.data);
  },

  /**
   * Reject payment
   * BACKEND: POST /api/v1/admin/service-requests/treasury/payments/{id}/reject
   */
  rejectPayment: async (
    paymentId: string,
    request: PaymentRejectionRequest
  ): Promise<PaymentActionResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}/reject`,
      { reason: request.reason }
    );
    return toCamelCase<PaymentActionResponse>(response.data);
  },

  /**
   * Escalate payment to supervisor
   * BACKEND: POST /api/v1/admin/service-requests/treasury/payments/{id}/escalate
   */
  escalatePayment: async (
    paymentId: string,
    request: { reason: string; level?: string }
  ): Promise<PaymentActionResponse> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}/escalate`,
      { reason: request.reason, level: request.level || 'medium' }
    );
    return toCamelCase<PaymentActionResponse>(response.data);
  },

  /**
   * Reassign payment to another treasury agent (supervisor only)
   * BACKEND: POST /api/v1/admin/service-requests/treasury/payments/{id}/reassign
   */
  reassignPayment: async (
    paymentId: string,
    targetAgentProfileId: string,
    reason?: string
  ): Promise<{ success: boolean; targetAgentName: string }> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}/reassign`,
      { target_agent_profile_id: targetAgentProfileId, reason }
    );
    return toCamelCase<{ success: boolean; targetAgentName: string }>(response.data);
  },

  /**
   * Validate all payments in a batch
   * BACKEND: POST /api/v1/admin/service-requests/treasury/batch/{batchId}/validate
   */
  validateBatchPayments: async (
    batchId: string,
    comment?: string
  ): Promise<{ success: boolean; paymentsValidated: number; batchReference?: string; error?: string }> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/batch/${batchId}/validate`,
      comment ? { comment } : {}
    );
    return toCamelCase<{ success: boolean; paymentsValidated: number; batchReference?: string; error?: string }>(response.data);
  },

  /**
   * Get payments escalated by current agent
   * BACKEND: GET /api/v1/admin/service-requests/treasury/payments/my-escalations
   */
  getMyEscalations: async (
    params: { page?: number; pageSize?: number } = {}
  ): Promise<PendingPaymentsListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      limit: params.pageSize || 20,
    };

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/my-escalations`,
      { params: queryParams }
    );

    const data = response.data;
    const payments = (data.payments as Record<string, unknown>[]) || [];
    return {
      payments: payments.map(transformPayment),
      total: (data.total as number) || 0,
      page: (data.page as number) || 1,
      pageSize: (data.page_size as number) || 20,
      isSupervisor: (data.is_supervisor as boolean) || false,
      isMainOffice: (data.is_main_office as boolean) || false,
    };
  },

  // -------------------------------------------------------------------------
  // Bank Transactions (Reconciliation)
  // -------------------------------------------------------------------------

  /**
   * Get unreconciled transactions
   * BACKEND: GET /api/v1/webhooks/transactions/unreconciled
   */
  getUnreconciledTransactions: async (
    params: BankTransactionParams = {}
  ): Promise<BankTransactionListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
      ...(params.search ? { search: params.search } : {}),
      ...(params.status ? { status: params.status } : {}),
    };

    const response = await apiClient.get<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/transactions/unreconciled`,
      { params: queryParams }
    );

    const data = response.data;
    const transactions = (data.transactions as Record<string, unknown>[]) || [];
    return {
      transactions: transactions.map(transformTransaction),
      total: (data.total as number) || 0,
      page: (data.page as number) || 1,
      pageSize: (data.page_size as number) || 20,
    };
  },

  /**
   * Get single transaction
   * BACKEND: GET /api/v1/webhooks/transactions/{id}
   */
  getTransaction: async (transactionId: string): Promise<BankTransaction> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/transactions/${transactionId}`
    );
    return transformTransaction(response.data);
  },

  /**
   * Manual reconciliation
   * BACKEND: POST /api/v1/webhooks/transactions/reconcile
   */
  reconcileTransaction: async (
    request: ReconcileRequest
  ): Promise<BankTransaction> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/transactions/reconcile`,
      {
        bank_transaction_id: request.bankTransactionId,
        service_payment_id: request.servicePaymentId,
      }
    );
    return transformTransaction(response.data);
  },

  /**
   * Search completed service_payments for manual reconciliation ComboBox
   */
  searchPaymentsForReconciliation: async (
    q: string,
    currency?: string
  ): Promise<SearchPaymentResult[]> => {
    const params: Record<string, string> = { q };
    if (currency) params.currency = currency;
    const response = await apiClient.get<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/transactions/search-payments`,
      { params }
    );
    const payments = (response.data.payments as Record<string, unknown>[]) || [];
    return payments.map((p) => toCamelCase<SearchPaymentResult>(p));
  },

  // --- Reconciliation Suggestions (Phase 5) -----

  getReconciliationSuggestions: async (limit: number = 50) => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/reconciliation/suggestions`,
      { params: { limit: limit.toString() } }
    );
    return toCamelCase<ReconciliationSuggestionsResponse>(response.data);
  },

  autoMatchReconciliation: async (threshold: number = 80) => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/reconciliation/auto-match`,
      {},
      { params: { threshold: threshold.toString() } }
    );
    return toCamelCase<AutoMatchResponse>(response.data);
  },

  // -------------------------------------------------------------------------
  // Bank Configurations
  // -------------------------------------------------------------------------

  /**
   * List bank configurations
   * BACKEND: GET /api/v1/webhooks/bank-configurations
   */
  getBankConfigurations: async (
    activeOnly: boolean = true
  ): Promise<BankConfiguration[]> => {
    const response = await apiClient.get<Record<string, unknown>[]>(
      `${WEBHOOKS_BASE}/bank-configurations`,
      { params: { active_only: activeOnly } }
    );
    return response.data.map(transformBankConfig);
  },

  /**
   * Create bank configuration
   * BACKEND: POST /api/v1/webhooks/bank-configurations
   */
  createBankConfiguration: async (
    config: BankConfigurationCreate
  ): Promise<BankConfiguration> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/bank-configurations`,
      {
        bank_code: config.bankCode,
        bank_name: config.bankName,
        api_endpoint: config.apiEndpoint,
        api_version: config.apiVersion,
        api_key_encrypted: config.apiKeyEncrypted,
        webhook_secret: config.webhookSecret,
        treasury_account_number: config.treasuryAccountNumber,
        is_active: config.isActive ?? true,
        supports_webhooks: config.supportsWebhooks ?? false,
        supports_direct_integration: config.supportsDirectIntegration ?? false,
        gateway_type: config.gatewayType || null,
        supported_payment_methods: config.supportedPaymentMethods || [],
        is_primary: config.isPrimary ?? false,
      }
    );
    return transformBankConfig(response.data);
  },

  /**
   * Update bank configuration
   * BACKEND: PUT /api/v1/webhooks/bank-configurations/{id}
   */
  updateBankConfiguration: async (
    configId: number,
    update: BankConfigurationUpdate
  ): Promise<BankConfiguration> => {
    const payload: Record<string, unknown> = {};
    if (update.bankName !== undefined) payload.bank_name = update.bankName;
    if (update.apiEndpoint !== undefined) payload.api_endpoint = update.apiEndpoint;
    if (update.apiVersion !== undefined) payload.api_version = update.apiVersion;
    if (update.apiKeyEncrypted !== undefined) payload.api_key_encrypted = update.apiKeyEncrypted;
    if (update.webhookSecret !== undefined) payload.webhook_secret = update.webhookSecret;
    if (update.treasuryAccountNumber !== undefined) payload.treasury_account_number = update.treasuryAccountNumber;
    if (update.isActive !== undefined) payload.is_active = update.isActive;
    if (update.supportsWebhooks !== undefined) payload.supports_webhooks = update.supportsWebhooks;
    if (update.supportsDirectIntegration !== undefined) payload.supports_direct_integration = update.supportsDirectIntegration;
    if (update.gatewayType !== undefined) payload.gateway_type = update.gatewayType || null;
    if (update.supportedPaymentMethods !== undefined) payload.supported_payment_methods = update.supportedPaymentMethods;
    if (update.isPrimary !== undefined) payload.is_primary = update.isPrimary;

    const response = await apiClient.put<Record<string, unknown>>(
      `${WEBHOOKS_BASE}/bank-configurations/${configId}`,
      payload
    );
    return transformBankConfig(response.data);
  },

  // -------------------------------------------------------------------------
  // Dashboard Stats
  // -------------------------------------------------------------------------

  /**
   * Get treasury dashboard stats
   * BACKEND: GET /api/v1/admin/service-requests/treasury/stats/dashboard
   */
  getDashboardStats: async (): Promise<TreasuryStats> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/dashboard`
    );

    const data = response.data;
    return {
      pendingValidationCount: (data.pending_validation_count as number) || 0,
      unreconciledCount: (data.unreconciled_count as number) || 0,
      todayValidatedCount: (data.today_validated_count as number) || 0,
      todayValidatedAmount: (data.today_validated_amount as number) || 0,
      currency: (data.currency as string) || 'XAF',
    };
  },

  // -------------------------------------------------------------------------
  // Payment Method Configurations
  // -------------------------------------------------------------------------

  /**
   * List payment method configurations
   * BACKEND: GET /api/v1/admin/service-requests/payment-methods
   */
  getPaymentMethods: async (activeOnly: boolean = false): Promise<PaymentMethodConfig[]> => {
    const response = await apiClient.get<Record<string, unknown>[]>(
      `${TREASURY_BASE}/payment-methods`,
      { params: { active_only: activeOnly } }
    );
    return response.data.map((item) => toCamelCase<PaymentMethodConfig>(item));
  },

  /**
   * Get single payment method
   * BACKEND: GET /api/v1/admin/service-requests/payment-methods/{code}
   */
  getPaymentMethod: async (code: string): Promise<PaymentMethodConfig> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/payment-methods/${code}`
    );
    return toCamelCase<PaymentMethodConfig>(response.data);
  },

  /**
   * Create payment method configuration
   * BACKEND: POST /api/v1/admin/service-requests/payment-methods
   * Note: Translations (FR/EN) are managed via entity_translations table
   */
  createPaymentMethod: async (config: PaymentMethodConfigCreate): Promise<PaymentMethodConfig> => {
    const payload: Record<string, unknown> = {
      code: config.code,
      label_es: config.labelEs,
    };
    if (config.processorType !== undefined) payload.processor_type = config.processorType;
    if (config.requiresPhone !== undefined) payload.requires_phone = config.requiresPhone;
    if (config.requiresRedirect !== undefined) payload.requires_redirect = config.requiresRedirect;
    if (config.requiresAgentValidation !== undefined) payload.requires_agent_validation = config.requiresAgentValidation;
    if (config.isActive !== undefined) payload.is_active = config.isActive;
    if (config.displayOrder !== undefined) payload.display_order = config.displayOrder;
    if (config.icon !== undefined) payload.icon = config.icon;
    if (config.minAmount !== undefined) payload.min_amount = config.minAmount;
    if (config.maxAmount !== undefined) payload.max_amount = config.maxAmount;
    if (config.feesPercentage !== undefined) payload.fees_percentage = config.feesPercentage;
    if (config.feesFixed !== undefined) payload.fees_fixed = config.feesFixed;

    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/payment-methods`,
      payload
    );
    return toCamelCase<PaymentMethodConfig>(response.data);
  },

  /**
   * Update payment method configuration
   * BACKEND: PUT /api/v1/admin/service-requests/payment-methods/{code}
   * Note: Translations (FR/EN) are managed via entity_translations table
   */
  updatePaymentMethod: async (
    code: string,
    update: PaymentMethodConfigUpdate
  ): Promise<PaymentMethodConfig> => {
    const payload: Record<string, unknown> = {};
    if (update.labelEs !== undefined) payload.label_es = update.labelEs;
    if (update.processorType !== undefined) payload.processor_type = update.processorType;
    if (update.requiresPhone !== undefined) payload.requires_phone = update.requiresPhone;
    if (update.requiresRedirect !== undefined) payload.requires_redirect = update.requiresRedirect;
    if (update.requiresAgentValidation !== undefined) payload.requires_agent_validation = update.requiresAgentValidation;
    if (update.isActive !== undefined) payload.is_active = update.isActive;
    if (update.displayOrder !== undefined) payload.display_order = update.displayOrder;
    if (update.icon !== undefined) payload.icon = update.icon;
    if (update.minAmount !== undefined) payload.min_amount = update.minAmount;
    if (update.maxAmount !== undefined) payload.max_amount = update.maxAmount;
    if (update.feesPercentage !== undefined) payload.fees_percentage = update.feesPercentage;
    if (update.feesFixed !== undefined) payload.fees_fixed = update.feesFixed;

    const response = await apiClient.put<Record<string, unknown>>(
      `${TREASURY_BASE}/payment-methods/${code}`,
      payload
    );
    return toCamelCase<PaymentMethodConfig>(response.data);
  },

  /**
   * Delete payment method configuration
   * BACKEND: DELETE /api/v1/admin/service-requests/payment-methods/{code}
   */
  deletePaymentMethod: async (code: string): Promise<void> => {
    await apiClient.delete(`${TREASURY_BASE}/payment-methods/${code}`);
  },

  /**
   * Reorder payment methods
   * BACKEND: PATCH /api/v1/admin/service-requests/payment-methods/reorder
   */
  reorderPaymentMethods: async (request: PaymentMethodReorderRequest): Promise<PaymentMethodConfig[]> => {
    const response = await apiClient.patch<Record<string, unknown>[]>(
      `${TREASURY_BASE}/payment-methods/reorder`,
      { order: request.order }
    );
    return response.data.map((item) => toCamelCase<PaymentMethodConfig>(item));
  },

  // -------------------------------------------------------------------------
  // Audit & Tracabilite (Phase 1A)
  // -------------------------------------------------------------------------

  /**
   * Get audit entries (global or filtered)
   * BACKEND: GET /api/v1/admin/service-requests/treasury/audit
   */
  getAuditEntries: async (params: AuditParams = {}): Promise<AuditListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
    };

    if (params.paymentId) queryParams.payment_id = params.paymentId;
    if (params.agentProfileId) queryParams.agent_profile_id = params.agentProfileId;
    if (params.action) queryParams.action = params.action;
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/audit`,
      { params: queryParams }
    );

    const data = response.data;
    const entries = (data.entries as Record<string, unknown>[]) || [];
    return {
      entries: entries.map((e) => toCamelCase<AuditEntry>(e)),
      total: (data.total as number) || 0,
      page: (data.page as number) || 1,
      pageSize: (data.page_size as number) || 20,
    };
  },

  /**
   * Get complete audit history for a specific payment
   * BACKEND: GET /api/v1/admin/service-requests/treasury/payments/{id}/audit
   */
  getPaymentAuditHistory: async (paymentId: string): Promise<PaymentAuditDetail> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/payments/${paymentId}/audit`
    );

    const data = response.data;
    const timeline = (data.timeline as Record<string, unknown>[]) || [];
    return {
      paymentId: (data.payment_id as string) || paymentId,
      paymentReference: (data.payment_reference as string) || '',
      serviceRequestId: data.service_request_id as string | undefined,
      serviceRequestReference: data.service_request_reference as string | undefined,
      workflowCode: data.workflow_code as string | undefined,
      currentStatus: data.current_status as string || 'submitted',
      createdAt: (data.created_at as string) || '',
      timeline: timeline.map((e) => toCamelCase<AuditEntry>(e)),
      totalProcessingMinutes: data.total_processing_minutes as number | undefined,
    } as PaymentAuditDetail;
  },

  // -------------------------------------------------------------------------
  // SLA Stats (Phase 1B)
  // -------------------------------------------------------------------------

  /**
   * Get SLA statistics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/stats/sla
   */
  getSLAStats: async (paymentMethod?: string): Promise<SLAStats> => {
    const queryParams: Record<string, string | undefined> = {};
    if (paymentMethod) queryParams.payment_method = paymentMethod;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/sla`,
      { params: queryParams }
    );

    const data = response.data;

    // Transform by_payment_method nested snake_case to camelCase
    let byPaymentMethod: SLAStats['byPaymentMethod'] = undefined;
    const rawByMethod = data.by_payment_method as Record<string, Record<string, number>> | undefined;
    if (rawByMethod) {
      byPaymentMethod = {};
      for (const [method, stats] of Object.entries(rawByMethod)) {
        byPaymentMethod[method] = {
          total: stats.total || 0,
          onTime: stats.on_time || 0,
          warning: stats.warning || 0,
          critical: stats.critical || 0,
          breached: stats.breached || 0,
        };
      }
    }

    return {
      totalPending: (data.total_pending as number) || 0,
      onTime: (data.on_time as number) || 0,
      warning: (data.warning as number) || 0,
      critical: (data.critical as number) || 0,
      breached: (data.breached as number) || 0,
      avgProcessingMinutes: data.avg_processing_minutes as number | undefined,
      maxProcessingMinutes: data.max_processing_minutes as number | undefined,
      slaRespectRate: (data.sla_respect_rate as number) || 100,
      byPaymentMethod,
    };
  },

  // -------------------------------------------------------------------------
  // Anomalies (Phase 2A)
  // -------------------------------------------------------------------------

  /**
   * Get anomalies list with filters
   * BACKEND: GET /api/v1/admin/service-requests/treasury/anomalies
   */
  getAnomalies: async (params: AnomalyParams = {}): Promise<AnomalyListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
    };

    if (params.status) queryParams.status = params.status;
    if (params.severity) queryParams.severity = params.severity;
    if (params.anomalyType) queryParams.anomaly_type = params.anomalyType;
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies`,
      { params: queryParams }
    );

    const data = response.data;
    const anomalies = (data.anomalies as Record<string, unknown>[]) || [];
    const summary = data.summary as Record<string, number> | undefined;

    return {
      anomalies: anomalies.map((a) => toCamelCase<Anomaly>(a)),
      total: (data.total as number) || 0,
      summary: {
        open: summary?.open || 0,
        investigating: summary?.investigating || 0,
        resolved: summary?.resolved || 0,
        falsePositive: summary?.false_positive || 0,
        escalated: summary?.escalated || 0,
        total: summary?.total || 0,
      },
    };
  },

  /**
   * Get single anomaly details
   * BACKEND: GET /api/v1/admin/service-requests/treasury/anomalies/{id}
   */
  getAnomaly: async (anomalyId: string): Promise<Anomaly> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies/${anomalyId}`
    );
    return toCamelCase<Anomaly>(response.data);
  },

  /**
   * Create manual anomaly
   * BACKEND: POST /api/v1/admin/service-requests/treasury/anomalies
   */
  createAnomaly: async (request: AnomalyCreateRequest): Promise<Anomaly> => {
    const payload: Record<string, unknown> = {
      entity_type: request.entityType,
      entity_id: request.entityId,
      anomaly_type: request.anomalyType,
      severity: request.severity,
      title: request.title,
    };
    if (request.description) payload.description = request.description;
    if (request.affectedAmount) payload.affected_amount = request.affectedAmount;
    if (request.relatedEntities) payload.related_entities = request.relatedEntities;

    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies`,
      payload
    );
    return toCamelCase<Anomaly>(response.data);
  },

  /**
   * Update anomaly status
   * BACKEND: PATCH /api/v1/admin/service-requests/treasury/anomalies/{id}/status
   */
  updateAnomalyStatus: async (
    anomalyId: string,
    request: AnomalyStatusUpdateRequest
  ): Promise<Anomaly> => {
    const payload: Record<string, unknown> = {
      new_status: request.newStatus,
    };
    if (request.comment) payload.comment = request.comment;
    if (request.resolution) payload.resolution = request.resolution;

    const response = await apiClient.patch<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies/${anomalyId}/status`,
      payload
    );
    return toCamelCase<Anomaly>(response.data);
  },

  /**
   * Get anomaly action history
   * BACKEND: GET /api/v1/admin/service-requests/treasury/anomalies/{id}/actions
   */
  getAnomalyActions: async (anomalyId: string): Promise<AnomalyAction[]> => {
    const response = await apiClient.get<Record<string, unknown>[]>(
      `${TREASURY_BASE}/anomalies/${anomalyId}/actions`
    );
    return response.data.map((a) => toCamelCase<AnomalyAction>(a));
  },

  /**
   * Add comment to anomaly
   * BACKEND: POST /api/v1/admin/service-requests/treasury/anomalies/{id}/comment
   */
  addAnomalyComment: async (anomalyId: string, comment: string): Promise<AnomalyAction> => {
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies/${anomalyId}/comment`,
      { comment }
    );
    return toCamelCase<AnomalyAction>(response.data);
  },

  /**
   * Run automatic anomaly detection
   * BACKEND: POST /api/v1/admin/service-requests/treasury/anomalies/detect
   */
  runAnomalyDetection: async (
    detectionTypes?: string[]
  ): Promise<{ detectedAt: string; anomaliesFound: number; byType: Record<string, unknown> }> => {
    const payload: Record<string, unknown> = {};
    if (detectionTypes && detectionTypes.length > 0) {
      payload.detection_types = detectionTypes;
    }

    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/anomalies/detect`,
      Object.keys(payload).length > 0 ? payload : undefined
    );

    const data = response.data;
    return {
      detectedAt: (data.detected_at as string) || new Date().toISOString(),
      anomaliesFound: (data.anomalies_found as number) || 0,
      byType: (data.by_type as Record<string, unknown>) || {},
    };
  },

  // -------------------------------------------------------------------------
  // Exports (Phase 2B)
  // -------------------------------------------------------------------------

  /**
   * Get exports list with filters
   * BACKEND: GET /api/v1/admin/service-requests/treasury/exports
   */
  getExports: async (params: ExportParams = {}): Promise<ExportListResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      page: params.page || 1,
      page_size: params.pageSize || 20,
    };

    if (params.status) queryParams.status = params.status;
    if (params.exportType) queryParams.export_type = params.exportType;
    if (params.periodStart) queryParams.period_start = params.periodStart;
    if (params.periodEnd) queryParams.period_end = params.periodEnd;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/exports`,
      { params: queryParams }
    );

    const data = response.data;
    const exports = (data.exports as Record<string, unknown>[]) || [];
    return {
      exports: exports.map((e) => toCamelCase<TreasuryExport>(e)),
      total: (data.total as number) || 0,
    };
  },

  /**
   * Get single export details
   * BACKEND: GET /api/v1/admin/service-requests/treasury/exports/{id}
   */
  getExport: async (exportId: string): Promise<TreasuryExport> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/exports/${exportId}`
    );
    return toCamelCase<TreasuryExport>(response.data);
  },

  /**
   * Get export templates
   * BACKEND: GET /api/v1/admin/service-requests/treasury/exports/templates
   */
  getExportTemplates: async (exportType?: string): Promise<ExportTemplate[]> => {
    const queryParams: Record<string, string | undefined> = {};
    if (exportType) queryParams.export_type = exportType;

    const response = await apiClient.get<Record<string, unknown>[]>(
      `${TREASURY_BASE}/exports/templates`,
      { params: queryParams }
    );
    return response.data.map((t) => toCamelCase<ExportTemplate>(t));
  },

  /**
   * Generate new export
   * BACKEND: POST /api/v1/admin/service-requests/treasury/exports/generate
   */
  generateExport: async (request: ExportCreateRequest): Promise<TreasuryExport> => {
    const payload: Record<string, unknown> = {
      export_type: request.exportType,
      export_format: request.exportFormat,
      period_start: request.periodStart,
      period_end: request.periodEnd,
    };
    if (request.filters) {
      payload.filters = {
        entity_code: request.filters.entityCode,
        payment_method: request.filters.paymentMethod,
        workflow_code: request.filters.workflowCode,
        status: request.filters.status,
      };
    }
    if (request.templateCode) payload.template_code = request.templateCode;

    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/exports/generate`,
      payload
    );
    return toCamelCase<TreasuryExport>(response.data);
  },

  /**
   * Download export file as blob
   * BACKEND: GET /api/v1/admin/service-requests/treasury/exports/{id}/download
   * Returns StreamingResponse (file content) with Content-Disposition header
   */
  downloadExport: async (exportId: string): Promise<ExportDownloadResponse> => {
    const response = await apiClient.get(
      `${TREASURY_BASE}/exports/${exportId}/download`,
      { responseType: 'blob' }
    );

    // Extract filename from Content-Disposition header
    const disposition = response.headers?.['content-disposition'] || '';
    const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
    const fileName = filenameMatch?.[1] || `export_${exportId}`;

    const blob = response.data as Blob;
    return { blob, fileName };
  },

  // -------------------------------------------------------------------------
  // KPIs & Performance Stats (Phase 4)
  // -------------------------------------------------------------------------

  /**
   * Get Treasury KPIs
   * BACKEND: GET /api/v1/admin/service-requests/treasury/stats/kpis
   */
  getKPIs: async (params: {
    period?: string;
    dateFrom?: string;
    dateTo?: string;
  } = {}): Promise<KPIResponse> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/kpis`,
      { params: queryParams }
    );

    const data = response.data;
    // Transform response with nested arrays
    const byPaymentMethod = (data.by_payment_method as Record<string, unknown>[]) || [];
    const byEntity = (data.by_entity as Record<string, unknown>[]) || [];
    const dailyTrend = (data.daily_trend as Record<string, unknown>[]) || [];
    const previousPeriod = data.previous_period as Record<string, unknown> | undefined;

    return {
      period: (data.period as string) || 'month',
      dateFrom: (data.date_from as string) || '',
      dateTo: (data.date_to as string) || '',
      totalCollected: (data.total_collected as number) || 0,
      totalTransactions: (data.total_transactions as number) || 0,
      avgTransactionAmount: (data.avg_transaction_amount as number) || 0,
      slaRespectRate: (data.sla_respect_rate as number) || 100,
      byPaymentMethod: byPaymentMethod.map((m) => toCamelCase<PaymentMethodKPI>(m)),
      byEntity: byEntity.map((m) => toCamelCase<EntityKPI>(m)),
      dailyTrend: dailyTrend.map((d) => toCamelCase<DailyTrend>(d)),
      previousPeriod: previousPeriod ? toCamelCase<PeriodComparison>(previousPeriod) : undefined,
    };
  },

  /**
   * Get Agent Performance Statistics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/stats/agents
   */
  getAgentPerformance: async (params: {
    period?: string;
    dateFrom?: string;
    dateTo?: string;
  } = {}): Promise<AgentPerformanceResponse> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/agents`,
      { params: queryParams }
    );

    const data = response.data;
    const agents = (data.agents as Record<string, unknown>[]) || [];

    return {
      period: (data.period as string) || 'month',
      dateFrom: (data.date_from as string) || '',
      dateTo: (data.date_to as string) || '',
      agents: agents.map((a) => toCamelCase<AgentStats>(a)),
      totalValidations: (data.total_validations as number) || 0,
      totalRejections: (data.total_rejections as number) || 0,
    };
  },

  // -------------------------------------------------------------------------
  // Analytics (Phase 5)
  // -------------------------------------------------------------------------

  /**
   * Get descriptive statistics for treasury metrics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/statistics
   */
  getStatistics: async (params: AnalyticsParams = {}): Promise<StatisticsResponse> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/statistics`,
      { params: queryParams }
    );

    return toCamelCase<StatisticsResponse>(response.data);
  },

  /**
   * Get correlation matrix between metrics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/correlations
   */
  getCorrelations: async (params: AnalyticsParams = {}): Promise<CorrelationMatrix> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/correlations`,
      { params: queryParams }
    );

    return toCamelCase<CorrelationMatrix>(response.data);
  },

  /**
   * Get trend analysis for metrics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/trends
   */
  getTrends: async (params: AnalyticsParams = {}): Promise<TrendsResponse> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/trends`,
      { params: queryParams }
    );

    return toCamelCase<TrendsResponse>(response.data);
  },

  /**
   * Get detected anomalies in metrics
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/anomalies
   */
  getAnalyticsAnomalies: async (params: AnalyticsParams = {}): Promise<AnomaliesResponse> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/anomalies`,
      { params: queryParams }
    );

    return toCamelCase<AnomaliesResponse>(response.data);
  },

  /**
   * Get predictions for a metric
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/predictions
   */
  getPredictions: async (params: PredictionParams = {}): Promise<PredictionsResponse> => {
    const queryParams: Record<string, string | number | undefined> = {
      period: params.period || 'month',
      horizon_days: params.horizonDays || 7,
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/predictions`,
      { params: queryParams }
    );

    return toCamelCase<PredictionsResponse>(response.data);
  },

  /**
   * Generate complete analytics report with findings and recommendations
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/report
   */
  getAnalyticsReport: async (params: ReportParams = {}): Promise<AnalyticsReport> => {
    const queryParams: Record<string, string | undefined> = {
      period: params.period || 'month',
      language: params.language || 'es',
    };
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/report`,
      { params: queryParams }
    );

    return toCamelCase<AnalyticsReport>(response.data);
  },

  /**
   * Explore custom variable analysis
   * BACKEND: GET /api/v1/admin/service-requests/treasury/analytics/explore
   */
  exploreAnalytics: async (params: ExploreParams): Promise<ExploreResponse> => {
    const queryParams: Record<string, string | undefined> = {
      primary_variable: params.primaryVariable,
      period: params.period || 'month',
    };
    if (params.secondaryVariable) queryParams.secondary_variable = params.secondaryVariable;
    if (params.dateFrom) queryParams.date_from = params.dateFrom;
    if (params.dateTo) queryParams.date_to = params.dateTo;

    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analytics/explore`,
      { params: queryParams }
    );

    return toCamelCase<ExploreResponse>(response.data);
  },

  // --- Supervisor Overview (Phase 3) -----

  getSupervisorOverview: async (days: number = 30, locationId?: string) => {
    const params: Record<string, string> = { days: days.toString() };
    if (locationId) params.location_id = locationId;
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/supervisor-overview`,
      { params }
    );
    return toCamelCase<SupervisorOverviewResponse>(response.data);
  },

  // --- Workload Dashboard (Carga de Trabajo) -----

  getWorkloadDashboard: async (days: number = 30): Promise<WorkloadDashboardResponse> => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/stats/workload-dashboard`,
      { params: { days: days.toString() } }
    );
    return toCamelCase<WorkloadDashboardResponse>(response.data);
  },

  // --- AI Analyst (Phase 4) -----

  askAnalyst: async (
    question: string,
    previousContext?: { question: string; toolsUsed: string[] },
    sessionId?: string
  ) => {
    const body: Record<string, unknown> = { question };
    if (previousContext) {
      body.previous_context = {
        question: previousContext.question,
        tools_used: previousContext.toolsUsed,
      };
    }
    if (sessionId) {
      body.session_id = sessionId;
    }
    const response = await apiClient.post<Record<string, unknown>>(
      `${TREASURY_BASE}/analyst/ask`,
      body
    );
    return toCamelCase<TreasuryAnalystResponse>(response.data);
  },

  getAnalystBriefing: async () => {
    const response = await apiClient.get<Record<string, unknown>>(
      `${TREASURY_BASE}/analyst/briefing`
    );
    return toCamelCase<TreasuryBriefingResponse>(response.data);
  },

  exportAnalystResponse: async (
    question: string,
    answer: string,
    artifacts: ArtifactData[],
    format: 'pdf' | 'markdown'
  ) => {
    const response = await apiClient.post(
      `${TREASURY_BASE}/analyst/export`,
      { question, answer, artifacts, format },
      { responseType: 'blob' }
    );
    const blob = response.data as Blob;
    const ext = format === 'pdf' ? 'pdf' : 'md';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analyst-${new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-')}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

export default treasuryApi;
