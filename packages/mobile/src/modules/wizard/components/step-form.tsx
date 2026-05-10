import { useState, useEffect, useCallback } from 'react';
import { StyleSheet, View, ScrollView } from 'react-native';
import { Text, Button, ActivityIndicator } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { FormConfig } from '../types/wizard.types';
import { DynamicFormRenderer } from './dynamic-form-renderer';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepFormProps {
  stepId: string;
  getFormConfig: (stepId: string) => Promise<FormConfig>;
  onSaveFormData: (formData: Record<string, unknown>, stepId?: string) => Promise<boolean>;
  isSaving: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepForm({ stepId, getFormConfig, onSaveFormData, isSaving }: StepFormProps) {
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();

  const [formConfig, setFormConfig] = useState<FormConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  // ── Load form config ─────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setIsLoading(true);
      setLoadError(null);
      try {
        const config = await getFormConfig(stepId);
        if (cancelled) return;
        setFormConfig(config);

        // Initialize values from current_value defaults
        const initial: Record<string, unknown> = {};
        for (const section of config.sections) {
          for (const field of section.fields) {
            if (field.current_value != null) {
              initial[field.key] = field.current_value;
            }
          }
        }
        setValues(initial);
      } catch {
        if (!cancelled) {
          setLoadError(t('wizard.form.loadError'));
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [stepId, getFormConfig, t]);

  // ── Value change ─────────────────────────────────────────────────────

  const handleValueChange = useCallback((key: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [key]: value }));
    // Clear error on change
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  // ── Validation ───────────────────────────────────────────────────────

  const validate = useCallback((): boolean => {
    if (!formConfig) return false;

    const newErrors: Record<string, string> = {};

    for (const section of formConfig.sections) {
      for (const field of section.fields) {
        if (field.required && !field.readonly) {
          const val = values[field.key];
          if (val == null || val === '') {
            newErrors[field.key] = t('wizard.form.fieldRequired');
          }
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formConfig, values, t]);

  // ── Submit ───────────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    if (!validate()) return;
    await onSaveFormData(values, stepId);
  }, [validate, onSaveFormData, values, stepId]);

  // ── Loading state ────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: spacing.sm }}>
          {t('wizard.form.loading')}
        </Text>
      </View>
    );
  }

  // ── Error state ──────────────────────────────────────────────────────

  if (loadError || !formConfig) {
    return (
      <View style={styles.centered}>
        <Text variant="bodyMedium" style={{ color: colors.error }}>
          {loadError ?? t('wizard.form.loadError')}
        </Text>
        <Button
          mode="outlined"
          onPress={() => {
            setIsLoading(true);
            setLoadError(null);
            getFormConfig(stepId)
              .then((config) => {
                setFormConfig(config);
                const initial: Record<string, unknown> = {};
                for (const section of config.sections) {
                  for (const field of section.fields) {
                    if (field.current_value != null) {
                      initial[field.key] = field.current_value;
                    }
                  }
                }
                setValues(initial);
              })
              .catch(() => setLoadError(t('wizard.form.loadError')))
              .finally(() => setIsLoading(false));
          }}
          style={{ marginTop: spacing.md, borderRadius: 8 }}
        >
          {t('common.retry')}
        </Button>
      </View>
    );
  }

  // ── Render form ──────────────────────────────────────────────────────

  return (
    <View style={styles.container}>
      <ScrollView
        contentContainerStyle={{ padding: spacing.md, paddingBottom: spacing.xxl }}
        keyboardShouldPersistTaps="handled"
      >
        {/* Form title */}
        {formConfig.title_es && (
          <Text
            variant="titleSmall"
            style={{ color: colors.onSurface, fontWeight: '600', marginBottom: spacing.sm }}
          >
            {formConfig.title_es}
          </Text>
        )}
        {formConfig.description_es && (
          <Text
            variant="bodySmall"
            style={{ color: colors.outline, marginBottom: spacing.md }}
          >
            {formConfig.description_es}
          </Text>
        )}

        {/* Dynamic form sections */}
        <DynamicFormRenderer
          sections={formConfig.sections}
          values={values}
          onValueChange={handleValueChange}
          errors={errors}
        />
      </ScrollView>

      {/* Submit button */}
      <View
        style={[
          styles.footer,
          {
            paddingHorizontal: spacing.md,
            paddingVertical: spacing.sm,
            borderTopColor: colors.outlineVariant,
          },
        ]}
      >
        <Button
          mode="contained"
          onPress={handleSubmit}
          loading={isSaving}
          disabled={isSaving}
          style={{ borderRadius: 8 }}
          contentStyle={{ paddingVertical: 4 }}
        >
          {t('wizard.form.next')}
        </Button>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  footer: { borderTopWidth: 1 },
});
