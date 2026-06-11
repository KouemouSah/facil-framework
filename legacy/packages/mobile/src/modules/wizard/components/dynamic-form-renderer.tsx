import { useState, useCallback } from 'react';
import { StyleSheet, View, Pressable, ScrollView } from 'react-native';
import {
  Text,
  TextInput,
  RadioButton,
  Checkbox,
  HelperText,
  Divider,
  Menu,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { FormSection, FormField, FormFieldOption } from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DynamicFormRendererProps {
  sections: FormSection[];
  values: Record<string, unknown>;
  onValueChange: (key: string, value: unknown) => void;
  errors?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// Select Picker (Paper Menu-based)
// ---------------------------------------------------------------------------

function SelectPicker({
  field,
  value,
  onSelect,
  error,
}: {
  field: FormField;
  value: string;
  onSelect: (value: string) => void;
  error?: string;
}) {
  const { colors, borderRadius } = useAppTheme();
  const [visible, setVisible] = useState(false);

  const selectedOption = field.options?.find((o) => o.value === value);
  const displayLabel = selectedOption?.label_es ?? field.placeholder_es ?? '';

  return (
    <View>
      <Menu
        visible={visible}
        onDismiss={() => setVisible(false)}
        anchor={
          <Pressable onPress={() => !field.readonly && setVisible(true)}>
            <TextInput
              mode="outlined"
              dense
              label={renderFieldLabel(field)}
              value={displayLabel}
              editable={false}
              right={<TextInput.Icon icon="chevron-down" onPress={() => !field.readonly && setVisible(true)} />}
              disabled={field.readonly}
              style={[styles.input, field.readonly && styles.readonlyInput]}
              outlineStyle={{ borderRadius: borderRadius.sm }}
              error={!!error}
              pointerEvents="none"
            />
          </Pressable>
        }
        contentStyle={{ maxHeight: 300 }}
      >
        <ScrollView style={{ maxHeight: 300 }}>
          {(field.options ?? []).map((option: FormFieldOption) => (
            <Menu.Item
              key={option.value}
              title={option.label_es}
              onPress={() => {
                onSelect(option.value);
                setVisible(false);
              }}
              titleStyle={
                option.value === value
                  ? { color: colors.primary, fontWeight: '600' }
                  : undefined
              }
            />
          ))}
        </ScrollView>
      </Menu>
      {error && (
        <HelperText type="error" visible>
          {error}
        </HelperText>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Label helper (adds red * for required)
// ---------------------------------------------------------------------------

function renderFieldLabel(field: FormField): string {
  return field.required ? `${field.label_es} *` : field.label_es;
}

// ---------------------------------------------------------------------------
// Single Field Renderer
// ---------------------------------------------------------------------------

function FormFieldComponent({
  field,
  value,
  onValueChange,
  error,
}: {
  field: FormField;
  value: unknown;
  onValueChange: (key: string, value: unknown) => void;
  error?: string;
}) {
  const { colors, borderRadius } = useAppTheme();
  const { t } = useTranslation();

  const stringValue = value != null ? String(value) : '';

  const handleChange = useCallback(
    (v: unknown) => onValueChange(field.key, v),
    [field.key, onValueChange],
  );

  switch (field.type) {
    // ── Text ───────────────────────────────────────────────────────────
    case 'text':
      return (
        <View style={styles.fieldContainer}>
          <TextInput
            mode="outlined"
            dense
            label={renderFieldLabel(field)}
            value={stringValue}
            onChangeText={(v) => handleChange(v)}
            placeholder={field.placeholder_es}
            disabled={field.readonly}
            style={[styles.input, field.readonly && styles.readonlyInput]}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={!!error}
          />
          {field.help_text_es && !error && (
            <HelperText type="info" visible>
              {field.help_text_es}
            </HelperText>
          )}
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Textarea ───────────────────────────────────────────────────────
    case 'textarea':
      return (
        <View style={styles.fieldContainer}>
          <TextInput
            mode="outlined"
            dense
            multiline
            numberOfLines={3}
            label={renderFieldLabel(field)}
            value={stringValue}
            onChangeText={(v) => handleChange(v)}
            placeholder={field.placeholder_es}
            disabled={field.readonly}
            style={[styles.input, field.readonly && styles.readonlyInput]}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={!!error}
          />
          {field.help_text_es && !error && (
            <HelperText type="info" visible>
              {field.help_text_es}
            </HelperText>
          )}
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Number ─────────────────────────────────────────────────────────
    case 'number':
      return (
        <View style={styles.fieldContainer}>
          <TextInput
            mode="outlined"
            dense
            label={renderFieldLabel(field)}
            value={stringValue}
            onChangeText={(v) => handleChange(v)}
            placeholder={field.placeholder_es}
            keyboardType="numeric"
            disabled={field.readonly}
            style={[styles.input, field.readonly && styles.readonlyInput]}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={!!error}
          />
          {field.help_text_es && !error && (
            <HelperText type="info" visible>
              {field.help_text_es}
            </HelperText>
          )}
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Date (text input for now) ──────────────────────────────────────
    case 'date':
      return (
        <View style={styles.fieldContainer}>
          <TextInput
            mode="outlined"
            dense
            label={renderFieldLabel(field)}
            value={stringValue}
            onChangeText={(v) => handleChange(v)}
            placeholder={field.placeholder_es ?? t('wizard.form.dateFormat')}
            keyboardType="numeric"
            disabled={field.readonly}
            right={<TextInput.Icon icon="calendar" />}
            style={[styles.input, field.readonly && styles.readonlyInput]}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={!!error}
          />
          {field.help_text_es && !error && (
            <HelperText type="info" visible>
              {field.help_text_es}
            </HelperText>
          )}
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Select ─────────────────────────────────────────────────────────
    case 'select':
      return (
        <View style={styles.fieldContainer}>
          <SelectPicker
            field={field}
            value={stringValue}
            onSelect={(v) => handleChange(v)}
            error={error}
          />
          {field.help_text_es && !error && (
            <HelperText type="info" visible>
              {field.help_text_es}
            </HelperText>
          )}
        </View>
      );

    // ── Radio ──────────────────────────────────────────────────────────
    case 'radio':
      return (
        <View style={styles.fieldContainer}>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginBottom: 4 }}>
            {renderFieldLabel(field)}
          </Text>
          <RadioButton.Group
            onValueChange={(v) => handleChange(v)}
            value={stringValue}
          >
            {(field.options ?? []).map((option: FormFieldOption) => (
              <RadioButton.Item
                key={option.value}
                label={option.label_es}
                value={option.value}
                style={styles.radioItem}
                disabled={field.readonly}
              />
            ))}
          </RadioButton.Group>
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Checkbox ───────────────────────────────────────────────────────
    case 'checkbox':
      return (
        <View style={styles.fieldContainer}>
          <Checkbox.Item
            label={renderFieldLabel(field)}
            status={value ? 'checked' : 'unchecked'}
            onPress={() => handleChange(!value)}
            disabled={field.readonly}
            style={styles.checkboxItem}
          />
          {field.help_text_es && (
            <HelperText type="info" visible style={{ marginTop: -4 }}>
              {field.help_text_es}
            </HelperText>
          )}
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );

    // ── Fallback ───────────────────────────────────────────────────────
    default:
      return (
        <View style={styles.fieldContainer}>
          <TextInput
            mode="outlined"
            dense
            label={renderFieldLabel(field)}
            value={stringValue}
            onChangeText={(v) => handleChange(v)}
            disabled={field.readonly}
            style={[styles.input, field.readonly && styles.readonlyInput]}
            outlineStyle={{ borderRadius: borderRadius.sm }}
            error={!!error}
          />
          {error && (
            <HelperText type="error" visible>
              {error}
            </HelperText>
          )}
        </View>
      );
  }
}

// ---------------------------------------------------------------------------
// Main Renderer
// ---------------------------------------------------------------------------

export function DynamicFormRenderer({
  sections,
  values,
  onValueChange,
  errors,
}: DynamicFormRendererProps) {
  const { colors, spacing } = useAppTheme();

  return (
    <View>
      {sections.map((section, sIdx) => (
        <View key={section.id} style={sIdx > 0 ? { marginTop: spacing.lg } : undefined}>
          {/* Section title */}
          <Text
            variant="titleSmall"
            style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 4 }}
          >
            {section.title_es}
          </Text>
          {section.description_es && (
            <Text
              variant="bodySmall"
              style={{ color: colors.outline, marginBottom: spacing.sm }}
            >
              {section.description_es}
            </Text>
          )}
          {section.source_document && (
            <Text
              variant="labelSmall"
              style={{ color: colors.info, marginBottom: spacing.sm }}
            >
              {section.source_document}
            </Text>
          )}
          <Divider style={{ marginBottom: spacing.sm }} />

          {/* Fields */}
          {section.fields.map((field) => {
            const fieldValue = values[field.key] ?? field.current_value ?? '';
            return (
              <FormFieldComponent
                key={field.key}
                field={field}
                value={fieldValue}
                onValueChange={onValueChange}
                error={errors?.[field.key]}
              />
            );
          })}
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  fieldContainer: { marginBottom: 8 },
  input: { fontSize: 14 },
  readonlyInput: { backgroundColor: '#F5F5F5' },
  radioItem: { paddingVertical: 2 },
  checkboxItem: { paddingVertical: 0, paddingLeft: 0 },
});
