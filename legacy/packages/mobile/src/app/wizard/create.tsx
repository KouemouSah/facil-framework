/**
 * Wizard Create — Entry point from service detail
 *
 * URL: /wizard/create?workflow_code=PASAPORTE&service_id=123
 *
 * Behavior:
 * 1. Loads workflow config from backend
 * 2. If workflow has a SELECTION step → show StepSelection first, then create session
 * 3. If workflow has NO selection step → create session immediately with defaults
 *
 * After session creation, redirects to wizard/[session-id]
 */

import { useCallback, useState, useEffect, useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, IconButton, ActivityIndicator, Button } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { useWizardSession } from '@modules/wizard';
import { StepSelection } from '@modules/wizard/components/step-selection';
import * as wizardApi from '@modules/wizard/services/wizard-api';
import type { WorkflowConfig, WorkflowStepConfig } from '@modules/wizard';
import { ReadinessBanner } from '@modules/vault';
import {
  useWorkflowTranslations,
  workflowNameKey,
} from '@modules/wizard/services/use-workflow-translations';

export default function WizardCreateScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { workflow_code } = useLocalSearchParams<{ workflow_code: string; service_id?: string }>();
  const { isAuthenticated } = useAuth();

  const { createSession, error: sessionError } = useWizardSession();
  const { tw } = useWorkflowTranslations();
  const [isCreating, setIsCreating] = useState(false);

  // Load workflow config to determine if there's a selection step
  const [workflowConfig, setWorkflowConfig] = useState<WorkflowConfig | null>(null);
  const [isLoadingConfig, setIsLoadingConfig] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});

  useEffect(() => {
    if (!workflow_code) return;
    setIsLoadingConfig(true);
    setConfigError(null);
    wizardApi
      .getWorkflowConfig(workflow_code)
      .then((config) => {
        setWorkflowConfig(config);
      })
      .catch((e) => {
        const msg = e instanceof Error ? e.message : 'Failed to load workflow config';
        setConfigError(msg);
      })
      .finally(() => {
        setIsLoadingConfig(false);
      });
  }, [workflow_code]);

  // Find the selection step in the workflow config (if any)
  const selectionStep = useMemo<WorkflowStepConfig | null>(() => {
    if (!workflowConfig?.steps) return null;
    return (
      workflowConfig.steps.find(
        (s) => s.type === 'selection' || s.type.startsWith('select'),
      ) ?? null
    );
  }, [workflowConfig]);

  // Handle form changes from StepSelection
  const handleFormChange = useCallback((key: string, value: unknown) => {
    setFormValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Create session and navigate to wizard
  const handleCreate = useCallback(
    async (selectionValues?: Record<string, unknown>) => {
      if (!workflow_code) return;
      setIsCreating(true);
      try {
        const vals = selectionValues || formValues;

        // Extract standard session creation fields from form values
        const solicitudType =
          (vals.solicitud_type as string) || 'expedicion';
        const subType = vals.sub_type as string | undefined;
        const motivo = vals.motivo as string | undefined;
        const isMinor =
          vals.is_minor === true ||
          vals.is_minor === 'true' ||
          undefined;

        const session = await createSession({
          workflow_code,
          solicitud_type: solicitudType,
          sub_type: subType,
          motivo,
          is_minor: isMinor,
        });
        router.replace(`/wizard/${session.session_id}` as never);
      } catch {
        // Error shown via useWizardSession error state
      } finally {
        setIsCreating(false);
      }
    },
    [workflow_code, createSession, router, formValues],
  );

  // Auto-create session if no selection step
  useEffect(() => {
    if (!isLoadingConfig && workflowConfig && !selectionStep && !isCreating) {
      handleCreate({});
    }
  }, [isLoadingConfig, workflowConfig, selectionStep]); // eslint-disable-line react-hooks/exhaustive-deps

  // -----------------------------------------------------------------------
  // Loading
  // -----------------------------------------------------------------------

  if (!workflow_code) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12 }}>
          {t('common.error')}
        </Text>
        <Button mode="outlined" onPress={() => router.back()} style={{ marginTop: 16 }}>
          {t('common.back')}
        </Button>
      </SafeAreaView>
    );
  }

  if (isLoadingConfig || (workflowConfig && !selectionStep && !sessionError)) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 12 }}>
          {t('wizard.loading')}
        </Text>
      </SafeAreaView>
    );
  }

  if (configError) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12, textAlign: 'center', paddingHorizontal: 24 }}>
          {configError}
        </Text>
        <Button mode="outlined" onPress={() => router.back()} style={{ marginTop: 16 }}>
          {t('common.back')}
        </Button>
      </SafeAreaView>
    );
  }

  // -----------------------------------------------------------------------
  // Render selection step
  // -----------------------------------------------------------------------

  const error = sessionError;

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Header */}
      <View style={[styles.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="arrow-left" size={24} onPress={() => router.back()} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }} numberOfLines={1}>
          {workflow_code
            ? tw(workflowNameKey(workflow_code), workflowConfig?.service_name_es || t('wizard.title'))
            : workflowConfig?.service_name_es || t('wizard.title')}
        </Text>
      </View>

      {/* Workflow info */}
      <View style={{ paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 }}>
        <Text variant="labelMedium" style={{ color: colors.outline }}>
          {workflow_code
            ? tw(workflowNameKey(workflow_code), workflowConfig?.service_name_es || workflow_code.replace(/_/g, ' '))
            : workflowConfig?.service_name_es || workflow_code.replace(/_/g, ' ')}
        </Text>
      </View>

      {/* Vault readiness pre-flight — only when authenticated; renders nothing
          while data is undefined so there's no skeleton flash. */}
      {isAuthenticated && workflow_code ? (
        <ReadinessBanner
          workflowCode={workflow_code}
          onPress={() => router.push('/documents' as never)}
        />
      ) : null}

      {error && (
        <View style={{ paddingHorizontal: 16, paddingVertical: 8 }}>
          <Text variant="bodySmall" style={{ color: colors.error }}>{error}</Text>
        </View>
      )}

      {selectionStep && (
        <StepSelection
          stepConfig={selectionStep}
          formValues={formValues}
          onFormChange={handleFormChange}
          onContinue={() => handleCreate(formValues)}
          isSaving={isCreating}
          workflowCode={workflow_code}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { justifyContent: 'center', alignItems: 'center' },
  topBar: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1 },
});
