/**
 * StepSelection — Dynamic selection step
 *
 * Reads config from the backend WorkflowStepConfig. Supports two formats:
 *
 * Format A (Residencia/TramitesVisado): config.sections[].fields[]
 *   - Sections with structured fields (radio, select, switch)
 *   - Supports show_when conditions on sections
 *
 * Format B (all other workflows): config.selection_type + config.options[]
 *   - Flat option list with radio buttons
 *   - Supports condition on individual options (e.g., applicant_type filter)
 *
 * Also handles custom step type "multi_selection" (checkboxes).
 */

import { useCallback, useMemo } from 'react';
import { StyleSheet, View, ScrollView, Pressable } from 'react-native';
import { Text, RadioButton, Switch, Button, Divider, Checkbox } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';
import type { WorkflowStepConfig } from '../types/wizard.types';
import {
  useWorkflowTranslations,
  stepTitleKey,
  optionLabelKey,
  optionDescKey,
  motivoKey,
  motivoDescKey,
} from '../services/use-workflow-translations';

// ---------------------------------------------------------------------------
// Types for config formats
// ---------------------------------------------------------------------------

interface SelectionFieldOption {
  value: string;
  label_es?: string;
}

interface SelectionField {
  key: string;
  type: string; // radio, select, switch, toggle
  label_es?: string;
  description_es?: string;
  required?: boolean;
  options?: SelectionFieldOption[];
}

interface SelectionSection {
  id: string;
  title_es?: string;
  description_es?: string;
  fields: SelectionField[];
  show_when?: Record<string, unknown>;
}

interface SelectionOption {
  value: string | boolean;
  label_es?: string;
  description_es?: string;
  icon?: string;
  tariff?: string | number;
  condition?: Record<string, unknown>;
}

interface MultiSelectionOption {
  id: string;
  label_es?: string;
  min_age?: number;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface StepSelectionProps {
  stepConfig: WorkflowStepConfig;
  formValues: Record<string, unknown>;
  onFormChange: (key: string, value: unknown) => void;
  onContinue: () => void;
  isSaving: boolean;
  /** Root workflow family for translation lookup (e.g. 'pasaporte', 'conducir') */
  workflowCode?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepSelection({
  stepConfig,
  formValues,
  onFormChange,
  onContinue,
  isSaving,
  workflowCode,
}: StepSelectionProps) {
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();
  const { tw } = useWorkflowTranslations();

  // Derive the workflow family name for translation lookups (e.g. 'pasaporte')
  const wfFamily = useMemo(() => {
    if (!workflowCode) return '';
    // Extract family: PASAPORTE_NUEVO → pasaporte, CONDUCIR_CANJE → conducir, etc.
    const lower = workflowCode.toLowerCase();
    // Known patterns
    if (lower.startsWith('pasaporte')) return 'pasaporte';
    if (lower.startsWith('conducir')) return 'conducir';
    if (lower.startsWith('contrato')) return 'contrato';
    if (lower.startsWith('residencia')) return 'residencia';
    if (lower.startsWith('vehiculo')) return 'vehiculo';
    if (lower.startsWith('prorroga') || lower.startsWith('visado') || lower.startsWith('permanencia') || lower.startsWith('salida_visado')) return 'visado';
    if (lower.startsWith('fp_carnet')) return 'carnet';
    if (lower.startsWith('fp_promocion')) return 'promocion';
    if (lower.startsWith('fp_permiso')) return 'permiso';
    if (lower.startsWith('fp_certificado')) return 'certificado';
    if (lower.startsWith('fp_verificacion')) return 'verificacion';
    if (lower === 'bundle_payment') return 'bundle';
    return lower;
  }, [workflowCode]);

  /**
   * Translate a label_es field. Tries workflow-specific option key first,
   * then motivo key, then falls back to the raw Spanish value.
   */
  const translateLabel = useCallback(
    (labelEs: string | undefined, optionValue?: string): string => {
      if (!labelEs) return optionValue || '';
      if (!wfFamily || !optionValue) return tw(stepTitleKey(labelEs), labelEs);

      // Try workflow-specific option key
      const optKey = optionLabelKey(wfFamily, optionValue);
      const result = tw(optKey, '');
      if (result && result !== optKey) return result;

      // Try motivo key (shared across workflows)
      const mKey = motivoKey(optionValue);
      const mResult = tw(mKey, '');
      if (mResult && mResult !== mKey) return mResult;

      // Try applicant type key (shared)
      const appKey = `workflow.option.applicant.${optionValue.toLowerCase()}`;
      const appResult = tw(appKey, '');
      if (appResult && appResult !== appKey) return appResult;

      return labelEs;
    },
    [tw, wfFamily],
  );

  /**
   * Translate a description_es field.
   */
  const translateDesc = useCallback(
    (descEs: string | undefined, optionValue?: string): string | undefined => {
      if (!descEs) return undefined;
      if (!wfFamily || !optionValue) return descEs;

      // Try workflow-specific option desc key
      const descKey = optionDescKey(wfFamily, optionValue);
      const result = tw(descKey, '');
      if (result && result !== descKey) return result;

      // Try motivo desc key
      const mDescKey = motivoDescKey(optionValue);
      const mResult = tw(mDescKey, '');
      if (mResult && mResult !== mDescKey) return mResult;

      // Try applicant type desc key
      const appDescKey = `workflow.option.applicant.${optionValue.toLowerCase()}.desc`;
      const appResult = tw(appDescKey, '');
      if (appResult && appResult !== appDescKey) return appResult;

      return descEs;
    },
    [tw, wfFamily],
  );

  /**
   * Translate a step/section title_es.
   */
  const translateTitle = useCallback(
    (titleEs: string | undefined): string => {
      if (!titleEs) return '';
      return tw(stepTitleKey(titleEs), titleEs);
    },
    [tw],
  );

  const cfg = stepConfig.config as Record<string, unknown> | undefined;

  // -----------------------------------------------------------------------
  // Format A: sections
  // -----------------------------------------------------------------------

  const sections = cfg?.sections as SelectionSection[] | undefined;

  const visibleSections = useMemo(() => {
    if (!sections) return undefined;
    return sections.filter((s) => {
      if (!s.show_when) return true;
      return Object.entries(s.show_when).every(
        ([k, v]) => String(formValues[k] ?? '') === String(v),
      );
    });
  }, [sections, formValues]);

  // -----------------------------------------------------------------------
  // Format B: selection_type + options
  // -----------------------------------------------------------------------

  const selectionType = cfg?.selection_type as string | undefined;
  const options = cfg?.options as SelectionOption[] | undefined;

  const filteredOptions = useMemo(() => {
    if (!options) return undefined;
    return options.filter((opt) => {
      if (!opt.condition) return true;
      return Object.entries(opt.condition).every(
        ([k, v]) => String(formValues[k] ?? '') === String(v),
      );
    });
  }, [options, formValues]);

  // -----------------------------------------------------------------------
  // Format C: multi_selection (checkboxes)
  // -----------------------------------------------------------------------

  const isMultiSelection = cfg?.type === 'multi_selection';
  const multiOptions = cfg?.options as MultiSelectionOption[] | undefined;
  const maxSelection = (cfg?.max_selection as number) || 10;

  const handleMultiToggle = useCallback(
    (optionId: string) => {
      const stepId = stepConfig.id;
      const current = (formValues[stepId] as string[] | undefined) || [];
      if (current.includes(optionId)) {
        onFormChange(stepId, current.filter((id) => id !== optionId));
      } else if (current.length < maxSelection) {
        onFormChange(stepId, [...current, optionId]);
      }
    },
    [formValues, stepConfig.id, onFormChange, maxSelection],
  );

  // -----------------------------------------------------------------------
  // Validation: can continue?
  // -----------------------------------------------------------------------

  const canContinue = useMemo(() => {
    // Format A: all required fields in visible sections must have values
    if (visibleSections) {
      const requiredKeys = visibleSections.flatMap((s) =>
        s.fields.filter((f) => f.required !== false).map((f) => f.key),
      );
      return requiredKeys.every(
        (key) => formValues[key] !== undefined && formValues[key] !== '',
      );
    }

    // Format B: selection_type must have a value
    if (selectionType && filteredOptions) {
      const val = formValues[selectionType];
      return val !== undefined && val !== '' && val !== null;
    }

    // Format C: multi_selection must have at least one
    if (isMultiSelection) {
      const selected = (formValues[stepConfig.id] as string[] | undefined) || [];
      return selected.length > 0;
    }

    return true;
  }, [visibleSections, selectionType, filteredOptions, isMultiSelection, formValues, stepConfig.id]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.md, paddingBottom: spacing.xxl }}>
      {/* Step title */}
      {stepConfig.title_es && (
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 4 }}>
          {translateTitle(stepConfig.title_es)}
        </Text>
      )}
      {stepConfig.description_es && (
        <Text variant="bodySmall" style={{ color: colors.outline, marginBottom: 12 }}>
          {stepConfig.description_es}
        </Text>
      )}

      {/* Format A: Sections with fields */}
      {visibleSections?.map((section) => (
        <View key={section.id} style={{ marginBottom: 16 }}>
          {section.title_es && (
            <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 4 }}>
              {translateTitle(section.title_es)}
            </Text>
          )}
          {section.description_es && (
            <Text variant="bodySmall" style={{ color: colors.outline, marginBottom: 8 }}>
              {section.description_es}
            </Text>
          )}

          {section.fields.map((field) => (
            <View key={field.key} style={{ marginBottom: 12 }}>
              {field.label_es && (
                <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant, marginBottom: 4 }}>
                  {translateLabel(field.label_es)}
                </Text>
              )}

              {/* Radio / Select */}
              {(field.type === 'radio' || field.type === 'select') && field.options && (
                <RadioButton.Group
                  onValueChange={(val) => onFormChange(field.key, val)}
                  value={String(formValues[field.key] ?? '')}
                >
                  {field.options.map((opt) => (
                    <RadioButton.Item
                      key={opt.value}
                      label={translateLabel(opt.label_es, opt.value)}
                      value={opt.value}
                      style={styles.radioItem}
                    />
                  ))}
                </RadioButton.Group>
              )}

              {/* Switch / Toggle */}
              {(field.type === 'switch' || field.type === 'toggle') && (
                <View style={styles.switchRow}>
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1 }}>
                    {field.description_es || translateLabel(field.label_es) || field.key}
                  </Text>
                  <Switch
                    value={String(formValues[field.key] ?? 'false') === 'true'}
                    onValueChange={(val) => onFormChange(field.key, String(val))}
                  />
                </View>
              )}
            </View>
          ))}

          <Divider style={{ marginTop: 4 }} />
        </View>
      ))}

      {/* Format B: Flat options with selection_type */}
      {!sections && selectionType && filteredOptions && (
        <>
          <RadioButton.Group
            onValueChange={(val) => onFormChange(selectionType, val)}
            value={String(formValues[selectionType] ?? '')}
          >
            {filteredOptions.map((opt) => {
              const optValue = String(opt.value);
              return (
                <Pressable
                  key={optValue}
                  onPress={() => onFormChange(selectionType, optValue)}
                  style={[
                    styles.optionCard,
                    {
                      borderColor:
                        String(formValues[selectionType]) === optValue
                          ? colors.primary
                          : colors.outlineVariant,
                      backgroundColor:
                        String(formValues[selectionType]) === optValue
                          ? colors.primaryContainer
                          : colors.surface,
                    },
                  ]}
                >
                  <View style={styles.optionRow}>
                    <RadioButton value={optValue} />
                    <View style={{ flex: 1, marginLeft: 4 }}>
                      <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '500' }}>
                        {translateLabel(opt.label_es, optValue)}
                      </Text>
                      {opt.description_es && (
                        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 2 }}>
                          {translateDesc(opt.description_es, optValue) || opt.description_es}
                        </Text>
                      )}
                      {opt.tariff != null && (
                        <Text variant="labelSmall" style={{ color: colors.primary, marginTop: 2 }}>
                          {typeof opt.tariff === 'number'
                            ? formatCurrency(opt.tariff)
                            : opt.tariff}
                        </Text>
                      )}
                    </View>
                    {opt.icon && (
                      <MaterialCommunityIcons
                        name={(opt.icon as keyof typeof MaterialCommunityIcons.glyphMap) || 'file-document-outline'}
                        size={20}
                        color={colors.outline}
                      />
                    )}
                  </View>
                </Pressable>
              );
            })}
          </RadioButton.Group>
        </>
      )}

      {/* Format C: Multi-selection (checkboxes) */}
      {!sections && !selectionType && isMultiSelection && multiOptions && (
        <>
          <Text variant="bodySmall" style={{ color: colors.outline, marginBottom: 8 }}>
            {t('wizard.selection.selectAtLeastOne')}
          </Text>
          {multiOptions.map((opt) => {
            const selected = (formValues[stepConfig.id] as string[] | undefined) || [];
            const isChecked = selected.includes(opt.id);
            return (
              <Pressable
                key={opt.id}
                onPress={() => handleMultiToggle(opt.id)}
                style={[
                  styles.optionCard,
                  {
                    borderColor: isChecked ? colors.primary : colors.outlineVariant,
                    backgroundColor: isChecked ? colors.primaryContainer : colors.surface,
                  },
                ]}
              >
                <View style={styles.optionRow}>
                  <Checkbox status={isChecked ? 'checked' : 'unchecked'} />
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1, marginLeft: 4 }}>
                    {translateLabel(opt.label_es, opt.id)}
                  </Text>
                </View>
              </Pressable>
            );
          })}
        </>
      )}

      {/* Continue button */}
      <Button
        mode="contained"
        onPress={onContinue}
        loading={isSaving}
        disabled={isSaving || !canContinue}
        style={{ marginTop: 24, borderRadius: 8 }}
        contentStyle={{ paddingVertical: 4 }}
      >
        {t('wizard.selection.continue')}
      </Button>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  radioItem: { paddingVertical: 2 },
  switchRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8 },
  optionCard: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
