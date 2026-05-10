/**
 * useWizardSession() — Main wizard hook
 *
 * Manages session lifecycle, document uploads, form data,
 * appointment selection, payment, and TTL countdown.
 *
 * Usage: const wizard = useWizardSession(sessionId?)
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import * as wizardApi from './wizard-api';
import { logger } from '@core/logging/logger';
import type {
  WizardSessionCreate,
  WizardSession,
  WorkflowConfig,
  DocumentPreview,
  DocumentConfirmRequest,
  FormConfig,
  PreparePaymentResult,
  InitiatePaymentRequest,
  InitiatePaymentResult,
  AppointmentLocationsResponse,
  AvailableDaysResponse,
  AvailableSlotsResponse,
  AppointmentSelectionRequest,
  AvailableSitesResponse,
  SiteSelectionRequest,
} from '../types/wizard.types';

export interface UseWizardSessionReturn {
  // State
  session: WizardSession | null;
  workflowConfig: WorkflowConfig | null;
  isLoading: boolean;
  isLoadingConfig: boolean;
  isSaving: boolean;
  error: string | null;

  // TTL
  timeRemaining: number;
  isExpiring: boolean; // < 5 min
  isExpired: boolean;

  // Session lifecycle
  createSession: (data: WizardSessionCreate) => Promise<WizardSession>;
  loadSession: (sessionId: string) => Promise<void>;
  cancelSession: (reason?: string) => Promise<void>;

  // Workflow config
  loadWorkflowConfig: (workflowCode: string) => Promise<WorkflowConfig | null>;

  // Documents
  previewDocument: (documentCode: string, fileUri: string, fileName: string) => Promise<DocumentPreview>;
  confirmDocument: (data: DocumentConfirmRequest) => Promise<void>;
  deleteDocument: (documentCode: string) => Promise<void>;
  uploadingDocuments: Set<string>;

  // Forms
  getFormConfig: (stepId: string) => Promise<FormConfig>;
  saveFormData: (formData: Record<string, unknown>, stepId?: string) => Promise<boolean>;

  // Appointments
  getLocations: () => Promise<AppointmentLocationsResponse>;
  getAvailableDays: (locationId: string, fromDate?: string) => Promise<AvailableDaysResponse>;
  getAvailableSlots: (locationId: string, fromDate?: string) => Promise<AvailableSlotsResponse>;
  saveAppointment: (data: AppointmentSelectionRequest) => Promise<void>;

  // Sites
  getAvailableSites: () => Promise<AvailableSitesResponse>;
  saveSite: (data: SiteSelectionRequest) => Promise<void>;

  // Payment
  preparePayment: () => Promise<PreparePaymentResult>;
  initiatePayment: (data: InitiatePaymentRequest) => Promise<InitiatePaymentResult>;

  // Utility
  clearError: () => void;
  refreshSession: () => Promise<void>;
}

export function useWizardSession(initialSessionId?: string): UseWizardSessionReturn {
  const [session, setSession] = useState<WizardSession | null>(null);
  const [workflowConfig, setWorkflowConfig] = useState<WorkflowConfig | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [uploadingDocuments, setUploadingDocuments] = useState<Set<string>>(new Set());

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sessionIdRef = useRef<string | null>(initialSessionId ?? null);

  // -----------------------------------------------------------------------
  // TTL Countdown
  // -----------------------------------------------------------------------

  const startTTLTimer = useCallback((ttlSeconds: number) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setTimeRemaining(ttlSeconds);
    timerRef.current = setInterval(() => {
      setTimeRemaining((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, []);

  const stopTTLTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopTTLTimer();
  }, [stopTTLTimer]);

  const isExpiring = timeRemaining > 0 && timeRemaining < 300; // < 5 min
  const isExpired = session !== null && timeRemaining <= 0;

  // -----------------------------------------------------------------------
  // Update session helper
  // -----------------------------------------------------------------------

  const updateSession = useCallback((newSession: WizardSession) => {
    setSession(newSession);
    sessionIdRef.current = newSession.session_id;
    if (newSession.ttl_seconds > 0) {
      startTTLTimer(newSession.ttl_seconds);
    }
  }, [startTTLTimer]);

  const getSessionId = useCallback((): string => {
    const id = sessionIdRef.current;
    if (!id) throw new Error('No active wizard session');
    return id;
  }, []);

  // -----------------------------------------------------------------------
  // Session Lifecycle
  // -----------------------------------------------------------------------

  const createSession = useCallback(async (data: WizardSessionCreate): Promise<WizardSession> => {
    setIsLoading(true);
    setError(null);
    try {
      const newSession = await wizardApi.createSession(data);
      updateSession(newSession);
      return newSession;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to create session';
      setError(msg);
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, [updateSession]);

  const loadSession = useCallback(async (sessionId: string): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const loaded = await wizardApi.getSession(sessionId);
      updateSession(loaded);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load session';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [updateSession]);

  const cancelSession = useCallback(async (reason?: string): Promise<void> => {
    try {
      await wizardApi.deleteSession(getSessionId(), reason);
      stopTTLTimer();
      setSession(null);
      sessionIdRef.current = null;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to cancel session';
      setError(msg);
    }
  }, [getSessionId, stopTTLTimer]);

  const refreshSession = useCallback(async (): Promise<void> => {
    try {
      const refreshed = await wizardApi.getSession(getSessionId());
      updateSession(refreshed);
    } catch {
      // Silent refresh failure
    }
  }, [getSessionId, updateSession]);

  // -----------------------------------------------------------------------
  // Workflow Config
  // -----------------------------------------------------------------------

  const loadWorkflowConfig = useCallback(async (workflowCode: string): Promise<WorkflowConfig | null> => {
    setIsLoadingConfig(true);
    try {
      const config = await wizardApi.getWorkflowConfig(workflowCode);
      setWorkflowConfig(config);
      return config;
    } catch (e) {
      // Non-fatal: the wizard can still work without config (fallback to legacy steps)
      logger.warn('useWizardSession', 'Failed to load workflow config', { err: String(e) });
      return null;
    } finally {
      setIsLoadingConfig(false);
    }
  }, []);

  // Auto-load workflow config when session is available
  useEffect(() => {
    if (session?.workflow_code && !workflowConfig) {
      loadWorkflowConfig(session.workflow_code);
    }
  }, [session?.workflow_code]); // eslint-disable-line react-hooks/exhaustive-deps

  // -----------------------------------------------------------------------
  // Documents
  // -----------------------------------------------------------------------

  const previewDocument = useCallback(async (
    documentCode: string, fileUri: string, fileName: string,
  ): Promise<DocumentPreview> => {
    setUploadingDocuments((prev) => new Set(prev).add(documentCode));
    setError(null);
    try {
      const preview = await wizardApi.previewDocument(getSessionId(), documentCode, fileUri, fileName);
      // Refresh session to get updated documents list
      await refreshSession();
      return preview;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Document upload failed';
      setError(msg);
      throw e;
    } finally {
      setUploadingDocuments((prev) => {
        const next = new Set(prev);
        next.delete(documentCode);
        return next;
      });
    }
  }, [getSessionId, refreshSession]);

  const confirmDocument = useCallback(async (data: DocumentConfirmRequest): Promise<void> => {
    setIsSaving(true);
    try {
      const updated = await wizardApi.confirmDocument(getSessionId(), data);
      updateSession(updated);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to confirm document';
      setError(msg);
      throw e;
    } finally {
      setIsSaving(false);
    }
  }, [getSessionId, updateSession]);

  const deleteDocument = useCallback(async (documentCode: string): Promise<void> => {
    try {
      const updated = await wizardApi.deleteDocument(getSessionId(), documentCode);
      updateSession(updated);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to delete document';
      setError(msg);
    }
  }, [getSessionId, updateSession]);

  // -----------------------------------------------------------------------
  // Forms
  // -----------------------------------------------------------------------

  const getFormConfig = useCallback(async (stepId: string): Promise<FormConfig> => {
    return wizardApi.getFormConfig(getSessionId(), stepId);
  }, [getSessionId]);

  const saveFormData = useCallback(async (
    formData: Record<string, unknown>, stepId?: string,
  ): Promise<boolean> => {
    setIsSaving(true);
    try {
      await wizardApi.saveFormData(getSessionId(), { form_data: formData, step_id: stepId });
      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save form data';
      setError(msg);
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [getSessionId]);

  // -----------------------------------------------------------------------
  // Appointments
  // -----------------------------------------------------------------------

  const getLocations = useCallback(async (): Promise<AppointmentLocationsResponse> => {
    return wizardApi.getAppointmentLocations(getSessionId());
  }, [getSessionId]);

  const getAvailableDays = useCallback(async (
    locationId: string, fromDate?: string,
  ): Promise<AvailableDaysResponse> => {
    return wizardApi.getAvailableDays(getSessionId(), locationId, fromDate);
  }, [getSessionId]);

  const getAvailableSlots = useCallback(async (
    locationId: string, fromDate?: string,
  ): Promise<AvailableSlotsResponse> => {
    return wizardApi.getAvailableSlots(getSessionId(), locationId, fromDate);
  }, [getSessionId]);

  const saveAppointment = useCallback(async (data: AppointmentSelectionRequest): Promise<void> => {
    setIsSaving(true);
    try {
      await wizardApi.selectAppointment(getSessionId(), data);
      await refreshSession();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save appointment';
      setError(msg);
      throw e;
    } finally {
      setIsSaving(false);
    }
  }, [getSessionId, refreshSession]);

  // -----------------------------------------------------------------------
  // Sites
  // -----------------------------------------------------------------------

  const getAvailableSites = useCallback(async (): Promise<AvailableSitesResponse> => {
    return wizardApi.getAvailableSites(getSessionId());
  }, [getSessionId]);

  const saveSite = useCallback(async (data: SiteSelectionRequest): Promise<void> => {
    setIsSaving(true);
    try {
      await wizardApi.selectSite(getSessionId(), data);
      await refreshSession();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save site selection';
      setError(msg);
      throw e;
    } finally {
      setIsSaving(false);
    }
  }, [getSessionId, refreshSession]);

  // -----------------------------------------------------------------------
  // Payment
  // -----------------------------------------------------------------------

  const preparePayment = useCallback(async (): Promise<PreparePaymentResult> => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await wizardApi.preparePayment(getSessionId());
      await refreshSession();
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to prepare payment';
      setError(msg);
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, [getSessionId, refreshSession]);

  const initiatePayment = useCallback(async (data: InitiatePaymentRequest): Promise<InitiatePaymentResult> => {
    setIsSaving(true);
    setError(null);
    try {
      const result = await wizardApi.initiatePayment(getSessionId(), data);
      if (result.success) {
        stopTTLTimer(); // Session persisted, no more TTL
        setSession(null); // Clear local session
      }
      return result;
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Payment failed';
      setError(msg);
      throw e;
    } finally {
      setIsSaving(false);
    }
  }, [getSessionId, stopTTLTimer]);

  // -----------------------------------------------------------------------
  // Auto-load session on mount
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (initialSessionId && !session) {
      loadSession(initialSessionId);
    }
  }, [initialSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // -----------------------------------------------------------------------
  // Return
  // -----------------------------------------------------------------------

  return {
    session,
    workflowConfig,
    isLoading,
    isLoadingConfig,
    isSaving,
    error,
    timeRemaining,
    isExpiring,
    isExpired,
    createSession,
    loadSession,
    cancelSession,
    loadWorkflowConfig,
    previewDocument,
    confirmDocument,
    deleteDocument,
    uploadingDocuments,
    getFormConfig,
    saveFormData,
    getLocations,
    getAvailableDays,
    getAvailableSlots,
    saveAppointment,
    getAvailableSites,
    saveSite,
    preparePayment,
    initiatePayment,
    clearError: () => setError(null),
    refreshSession,
  };
}
