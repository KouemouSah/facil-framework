/**
 * Wizard Session Screen — Dynamic multi-step wizard
 *
 * Steps are built dynamically from backend WorkflowConfig.steps.
 * No hardcoded step definitions.
 *
 * Step type mapping:
 *   selection / select_*    → StepSelection
 *   document_upload         → StepUpload
 *   form_review*            → StepForm
 *   appointment             → StepAppointment
 *   site_selection          → StepSiteSelection
 *   payment                 → StepPayment
 *   confirmation            → StepConfirmation
 *   custom                  → StepSelection (multi_selection)
 */

import { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { StyleSheet, View, Alert } from 'react-native';
import { Text, Button, IconButton, ActivityIndicator, Snackbar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useScreenProtection } from '@core/security/use-screen-protection';
import { useWizardSession } from '@modules/wizard';
import { WizardStepper } from '@modules/wizard/components/wizard-stepper';
import { TTLCountdown } from '@modules/wizard/components/ttl-countdown';

import { StepSelection } from '@modules/wizard/components/step-selection';
import { StepUpload } from '@modules/wizard/components/step-upload';
import { DocumentPreviewSheet } from '@modules/wizard/components/document-preview-sheet';
import { StepForm } from '@modules/wizard/components/step-form';
import { StepAppointment } from '@modules/wizard/components/step-appointment';
import { StepSiteSelection } from '@modules/wizard/components/step-site-selection';
import { StepPayment } from '@modules/wizard/components/step-payment';
import { StepConfirmation } from '@modules/wizard/components/step-confirmation';
import type { DocumentPreview, InitiatePaymentResult, WorkflowStepConfig } from '@modules/wizard';
import {
  useWorkflowTranslations,
  stepTitleKey,
  workflowNameKey,
} from '@modules/wizard/services/use-workflow-translations';

// ---------------------------------------------------------------------------
// Step types that we can render. Anything else is skipped.
// ---------------------------------------------------------------------------

const RENDERABLE_STEP_TYPES = new Set([
  'selection',
  'select_applicant_type',
  'document_upload',
  'form_review',
  'payment',
  'appointment',
  'site_selection',
  'confirmation',
  'custom',
]);

/**
 * Classify a backend step type into a renderable category.
 * form_review_1, form_review_2, form_review_3 → 'form_review'
 * selection, select_applicant_type → 'selection'
 */
function classifyStepType(type: string): string {
  if (type.startsWith('form_review')) return 'form_review';
  if (type.startsWith('select')) return 'selection';
  return type;
}

function isRenderableStep(step: WorkflowStepConfig, formValues: Record<string, unknown>): boolean {
  const cls = classifyStepType(step.type);
  if (!RENDERABLE_STEP_TYPES.has(cls)) return false;
  // Skip stamp_payment-type steps (shown in tariff breakdown)
  if (step.id.startsWith('stamp')) return false;

  // Evaluate step-level condition from config
  const cfg = step.config as Record<string, unknown> | undefined;
  const condition = cfg?.condition as Record<string, unknown> | undefined;
  if (condition) {
    for (const [key, expected] of Object.entries(condition)) {
      const actual = formValues[key];
      if (String(actual ?? '') !== String(expected)) return false;
    }
  }

  return true;
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function WizardSessionScreen() {
  useScreenProtection();
  const params = useLocalSearchParams<{ 'session-id': string }>();
  const sessionId = params['session-id'] ?? '';
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();

  const wizard = useWizardSession(sessionId);
  const {
    session,
    workflowConfig,
    isLoading,
    isLoadingConfig,
    isSaving,
    error,
    timeRemaining,
    isExpiring,
    isExpired,
  } = wizard;
  const { tw } = useWorkflowTranslations();

  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [documentPreview, setDocumentPreview] = useState<DocumentPreview | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [paymentResult, setPaymentResult] = useState<InitiatePaymentResult | null>(null);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const initialFormDataLoadedRef = useRef(false);

  // Restore form data from session ONLY on initial load
  // CRITICAL: Do NOT overwrite formValues after a save — causes race condition
  // where steps recalculate while step index is advancing, leading to redirects.
  useEffect(() => {
    if (session?.form_data && !initialFormDataLoadedRef.current) {
      initialFormDataLoadedRef.current = true;
      // Normalize all values to strings to prevent type coercion bugs
      const normalized: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(session.form_data)) {
        normalized[k] = v != null && typeof v !== 'object' ? String(v) : v;
      }
      setFormValues((prev) => ({ ...prev, ...normalized }));
    }
  }, [session?.form_data]);

  // -----------------------------------------------------------------------
  // Build steps dynamically from workflow config
  // -----------------------------------------------------------------------

  const steps = useMemo(() => {
    if (!workflowConfig?.steps || workflowConfig.steps.length === 0) return [];

    const filtered = workflowConfig.steps.filter((s) => isRenderableStep(s, formValues));

    // Inject site_selection for non-appointment workflows that don't have it
    const hasAppointmentStep = filtered.some((s) => s.type === 'appointment');
    const hasSiteSelectionStep = filtered.some((s) => s.type === 'site_selection');

    if (!hasAppointmentStep && !hasSiteSelectionStep) {
      // Insert before payment step
      const paymentIdx = filtered.findIndex((s) => s.type === 'payment');
      const insertIdx = paymentIdx >= 0 ? paymentIdx : filtered.length;
      const siteStep: WorkflowStepConfig = {
        number: 0,
        id: 'site_selection',
        type: 'site_selection',
        title_es: 'Sitio de tramitacion',
        is_inherited: false,
      };
      filtered.splice(insertIdx, 0, siteStep);
    }

    return filtered;
  }, [workflowConfig, formValues]);

  // Clamp step index if steps list shrinks (e.g., condition no longer met)
  const safeStepIndex = Math.min(currentStepIndex, Math.max(0, steps.length - 1));
  useEffect(() => {
    if (safeStepIndex !== currentStepIndex) {
      setCurrentStepIndex(safeStepIndex);
    }
  }, [safeStepIndex, currentStepIndex]);

  const currentStep = steps[safeStepIndex];
  const currentStepClass = currentStep ? classifyStepType(currentStep.type) : undefined;

  // -----------------------------------------------------------------------
  // Form change handler (for selection/custom steps)
  // -----------------------------------------------------------------------

  const handleFormChange = useCallback((key: string, value: unknown) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // -----------------------------------------------------------------------
  // Navigation
  // -----------------------------------------------------------------------

  const handleNext = useCallback(async () => {
    if (!session || !currentStep) return;

    // Save selection/custom data before advancing (aligned with web)
    if (currentStepClass === 'selection' || currentStepClass === 'custom') {
      const success = await wizard.saveFormData(formValues, currentStep.id);
      if (!success) return; // Error shown via hook
    }

    // Advance step index (no delay — aligned with web)
    if (safeStepIndex < steps.length - 1) {
      setCurrentStepIndex((prev) => prev + 1);
    }
  }, [session, currentStep, currentStepClass, safeStepIndex, steps.length, wizard, formValues]);

  const handlePrev = useCallback(() => {
    if (safeStepIndex > 0) {
      setCurrentStepIndex((prev) => prev - 1);
    }
  }, [safeStepIndex]);

  const handleCancel = useCallback(() => {
    Alert.alert(
      t('wizard.cancel'),
      t('wizard.cancelConfirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          style: 'destructive',
          onPress: async () => {
            await wizard.cancelSession();
            router.back();
          },
        },
      ],
    );
  }, [wizard, router, t]);

  // -----------------------------------------------------------------------
  // Loading states
  // -----------------------------------------------------------------------

  if ((isLoading || isLoadingConfig) && !session) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 12 }}>
          {t('wizard.loading')}
        </Text>
      </SafeAreaView>
    );
  }

  // Workflow config still loading after session is available
  if (session && isLoadingConfig && steps.length === 0) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 12 }}>
          {t('wizard.loading')}
        </Text>
      </SafeAreaView>
    );
  }

  // Workflow config failed to load — show error with retry button
  if (session && !isLoadingConfig && !workflowConfig && steps.length === 0) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="cloud-alert" size={48} color={colors.error} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', marginTop: 12, textAlign: 'center', paddingHorizontal: 24 }}>
          {tw('workflow.label.error_loading', t('wizard.configError', 'Error loading configuration'))}
        </Text>
        <View style={{ flexDirection: 'row', marginTop: 16, gap: 12 }}>
          <Button
            mode="contained"
            icon="refresh"
            onPress={() => {
              if (session?.workflow_code) {
                wizard.loadWorkflowConfig(session.workflow_code);
              }
            }}
          >
            {tw('workflow.label.retry', t('common.retry', 'Retry'))}
          </Button>
          <Button mode="outlined" onPress={() => router.back()}>
            {t('common.back')}
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  // Expired
  if (isExpired) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="clock-alert-outline" size={48} color={colors.error} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', marginTop: 12 }}>
          {t('wizard.sessionExpired')}
        </Text>
        <Button mode="contained" onPress={() => router.back()} style={{ marginTop: 16 }}>
          {t('common.back')}
        </Button>
      </SafeAreaView>
    );
  }

  // Error state
  if (!session && error) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12, textAlign: 'center', paddingHorizontal: 24 }}>
          {error}
        </Text>
        <Button mode="outlined" onPress={() => router.back()} style={{ marginTop: 16 }}>
          {t('common.back')}
        </Button>
      </SafeAreaView>
    );
  }

  if (!session) return null;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
      {/* Top bar: cancel + title + TTL */}
      <View style={[styles.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="close" size={22} onPress={handleCancel} />
        <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }} numberOfLines={1}>
          {session?.workflow_code
            ? tw(workflowNameKey(session.workflow_code), workflowConfig?.service_name_es || t('wizard.title'))
            : workflowConfig?.service_name_es || t('wizard.title')}
        </Text>
        <TTLCountdown timeRemaining={timeRemaining} isExpiring={isExpiring} />
      </View>

      {/* Stepper */}
      <View style={{ paddingHorizontal: spacing.md }}>
        <WizardStepper
          totalSteps={steps.length}
          currentStep={safeStepIndex}
          stepLabels={steps.map((s) => tw(stepTitleKey(s.title_es), s.title_es) || s.id)}
        />
      </View>

      {/* Step content */}
      <View style={styles.stepContent}>
        {/* Selection / Custom steps */}
        {currentStep && (currentStepClass === 'selection' || currentStepClass === 'custom') && (
          <StepSelection
            stepConfig={currentStep}
            formValues={formValues}
            onFormChange={handleFormChange}
            onContinue={handleNext}
            isSaving={isSaving}
            workflowCode={session?.workflow_code}
          />
        )}

        {/* Document Upload */}
        {currentStep && currentStep.type === 'document_upload' && (
          <StepUpload
            requiredDocuments={session.required_documents}
            uploadingDocuments={wizard.uploadingDocuments}
            onUploadDocument={wizard.previewDocument}
            onDeleteDocument={wizard.deleteDocument}
            onDocumentPreview={(preview) => {
              setDocumentPreview(preview);
              setShowPreview(true);
            }}
            sessionId={sessionId}
            workflowCode={session.workflow_code}
          />
        )}

        {/* Form Review (form_review_1, form_review_2, form_review_3, ...) */}
        {currentStep && currentStepClass === 'form_review' && (
          <StepForm
            stepId={currentStep.id}
            getFormConfig={wizard.getFormConfig}
            onSaveFormData={wizard.saveFormData}
            isSaving={isSaving}
          />
        )}

        {/* Appointment */}
        {currentStep && currentStep.type === 'appointment' && (
          <StepAppointment
            getLocations={wizard.getLocations}
            getAvailableDays={wizard.getAvailableDays}
            getAvailableSlots={wizard.getAvailableSlots}
            saveAppointment={wizard.saveAppointment}
            currentAppointment={session.appointment_data}
            isSaving={isSaving}
          />
        )}

        {/* Site Selection */}
        {currentStep && currentStep.type === 'site_selection' && (
          <StepSiteSelection
            getAvailableSites={wizard.getAvailableSites}
            saveSite={wizard.saveSite}
            currentSite={session.site_selection}
            isSaving={isSaving}
          />
        )}

        {/* Payment */}
        {currentStep && currentStep.type === 'payment' && !paymentResult && (
          <StepPayment
            sessionId={sessionId}
            preparePayment={wizard.preparePayment}
            initiatePayment={wizard.initiatePayment}
            isSaving={isSaving}
            onPaymentComplete={(result) => {
              setPaymentResult(result);
              // For gateway-redirect flows (BANGE Mobile Money) the user is now
              // either still in the in-app browser or has just been deep-linked
              // back to the app. Either way, send them straight to the
              // payment-result polling screen — the in-wizard confirmation step
              // is only meaningful for non-gateway flows (cash/check).
              if (result.success && result.redirect_url && result.service_request_id) {
                const params = new URLSearchParams({
                  session_id: sessionId,
                  service_request_id: result.service_request_id,
                });
                if (result.payment_id) params.set('payment_id', result.payment_id);
                router.replace(`/wizard/payment-result?${params.toString()}` as never);
                return;
              }
              // Non-gateway flows: advance to the inline confirmation step.
              const confirmIdx = steps.findIndex((s) => s.type === 'confirmation');
              if (confirmIdx >= 0) setCurrentStepIndex(confirmIdx);
            }}
          />
        )}

        {/* Confirmation */}
        {currentStep && currentStep.type === 'confirmation' && paymentResult && (
          <StepConfirmation
            result={paymentResult}
            onViewRequest={() => {
              if (paymentResult.service_request_id) {
                router.replace(`/(tabs)/requests/${paymentResult.service_request_id}` as never);
              }
            }}
            onGoHome={() => router.replace('/(tabs)' as never)}
          />
        )}
      </View>

      {/* Document preview bottom sheet */}
      <DocumentPreviewSheet
        visible={showPreview}
        onDismiss={() => setShowPreview(false)}
        preview={documentPreview}
        onConfirm={async (data) => {
          await wizard.confirmDocument(data);
          setShowPreview(false);
          setDocumentPreview(null);
        }}
        isConfirming={isSaving}
      />

      {/* Navigation buttons — hidden on selection (has its own button), appointment, site_selection, confirmation */}
      {currentStepClass !== 'selection' &&
        currentStepClass !== 'custom' &&
        currentStep?.type !== 'appointment' &&
        currentStep?.type !== 'site_selection' &&
        currentStep?.type !== 'confirmation' && (
          <View style={[styles.navBar, { backgroundColor: colors.surface, borderTopColor: colors.outlineVariant }]}>
            <Button
              mode="outlined"
              onPress={handlePrev}
              disabled={safeStepIndex === 0}
              style={{ flex: 1, marginRight: 8 }}
            >
              {t('common.previous')}
            </Button>
            <Button
              mode="contained"
              onPress={handleNext}
              disabled={safeStepIndex === steps.length - 1}
              loading={isSaving}
              style={{ flex: 1, borderRadius: 8 }}
            >
              {t('common.next')}
            </Button>
          </View>
        )}

      {/* Error snackbar */}
      <Snackbar visible={!!snackbar || !!error} onDismiss={() => { setSnackbar(null); wizard.clearError(); }} duration={4000}>
        {snackbar ?? error ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { justifyContent: 'center', alignItems: 'center' },
  topBar: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, paddingRight: 8 },
  stepContent: { flex: 1 },
  navBar: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16, borderTopWidth: 1 },
});
