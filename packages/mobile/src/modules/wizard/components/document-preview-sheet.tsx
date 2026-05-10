import { useState, useCallback, useMemo, useEffect } from 'react';
import { StyleSheet, View, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import {
  Text,
  Modal,
  Portal,
  TextInput,
  Button,
  Divider,
  IconButton,
} from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { DocumentPreview, DocumentConfirmRequest } from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DocumentPreviewSheetProps {
  visible: boolean;
  onDismiss: () => void;
  preview: DocumentPreview | null;
  onConfirm: (data: DocumentConfirmRequest) => Promise<void>;
  isConfirming: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getConfidenceColor(
  confidence: number,
  theme: { success: string; warning: string; error: string },
): string {
  if (confidence >= 80) return theme.success;
  if (confidence >= 50) return theme.warning;
  return theme.error;
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 80) return 'high';
  if (confidence >= 50) return 'medium';
  return 'low';
}

function flattenExtraction(
  extraction: Record<string, unknown>,
  prefix = '',
): { key: string; displayKey: string; value: string }[] {
  const entries: { key: string; displayKey: string; value: string }[] = [];

  for (const [key, val] of Object.entries(extraction)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (val !== null && typeof val === 'object' && !Array.isArray(val)) {
      entries.push(
        ...flattenExtraction(val as Record<string, unknown>, fullKey),
      );
    } else {
      entries.push({
        key: fullKey,
        displayKey: key.replace(/_/g, ' '),
        value: val != null ? String(val) : '',
      });
    }
  }

  return entries;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DocumentPreviewSheet({
  visible,
  onDismiss,
  preview,
  onConfirm,
  isConfirming,
}: DocumentPreviewSheetProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  // ── Editable field state ─────────────────────────────────────────────

  const extractedFields = useMemo(
    () => (preview ? flattenExtraction(preview.extraction) : []),
    [preview],
  );

  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [userNotes, setUserNotes] = useState('');

  // Reset state when a new preview is opened
  useEffect(() => {
    if (preview) {
      const initial: Record<string, string> = {};
      for (const field of flattenExtraction(preview.extraction)) {
        initial[field.key] = field.value;
      }
      setEditedValues(initial);
      setUserNotes('');
    }
  }, [preview]);

  const handleFieldChange = useCallback((key: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // ── Confirm handler ──────────────────────────────────────────────────

  const handleConfirm = useCallback(async () => {
    if (!preview) return;

    // Build confirmed_data from editedValues, converting back to nested if needed
    const confirmedData: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(editedValues)) {
      const parts = key.split('.');
      if (parts.length === 1) {
        confirmedData[key] = value;
      } else {
        // Rebuild nested structure
        let target: Record<string, unknown> = confirmedData;
        for (let i = 0; i < parts.length - 1; i++) {
          if (!target[parts[i]] || typeof target[parts[i]] !== 'object') {
            target[parts[i]] = {};
          }
          target = target[parts[i]] as Record<string, unknown>;
        }
        target[parts[parts.length - 1]] = value;
      }
    }

    await onConfirm({
      document_code: preview.document_code,
      confirmed_data: confirmedData,
      user_notes: userNotes || undefined,
    });
  }, [preview, editedValues, userNotes, onConfirm]);

  // ── Risk analysis warnings ───────────────────────────────────────────

  const riskWarnings = useMemo(() => {
    if (!preview?.risk_analysis) return [];
    const warnings: { label: string; level: string }[] = [];
    for (const [key, val] of Object.entries(preview.risk_analysis)) {
      if (val && typeof val === 'object' && 'level' in val) {
        const entry = val as { level: string; message?: string };
        if (entry.level === 'warning' || entry.level === 'error') {
          warnings.push({
            label: entry.message ?? key.replace(/_/g, ' '),
            level: entry.level,
          });
        }
      }
    }
    return warnings;
  }, [preview]);

  if (!preview) return null;

  const confidencePercent = Math.round(preview.confidence * 100);
  const confidenceColor = getConfidenceColor(confidencePercent, colors);
  const editable = preview.needs_correction;

  return (
    <Portal>
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        contentContainerStyle={[
          styles.modal,
          {
            backgroundColor: colors.surface,
            borderTopLeftRadius: borderRadius.lg,
            borderTopRightRadius: borderRadius.lg,
          },
        ]}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.flex}
        >
          {/* Header */}
          <View style={[styles.header, { paddingHorizontal: spacing.md }]}>
            <View style={styles.headerLeft}>
              <Text
                variant="titleSmall"
                style={{ color: colors.onSurface, fontWeight: '600' }}
                numberOfLines={1}
              >
                {preview.document_name ?? preview.document_code}
              </Text>
              <View style={styles.badgeRow}>
                {/* Confidence badge */}
                <View
                  style={[
                    styles.badge,
                    { backgroundColor: `${confidenceColor}18`, borderRadius: borderRadius.sm },
                  ]}
                >
                  <Text
                    variant="labelSmall"
                    style={{ color: confidenceColor, fontWeight: '600' }}
                  >
                    {confidencePercent}% {t(`wizard.preview.confidence.${getConfidenceLabel(confidencePercent)}`)}
                  </Text>
                </View>

                {/* Processor badge */}
                <View
                  style={[
                    styles.badge,
                    { backgroundColor: colors.surfaceVariant, borderRadius: borderRadius.sm },
                  ]}
                >
                  <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
                    {preview.processor === 'gemini' ? 'Gemini' : 'Tesseract'}
                  </Text>
                </View>
              </View>
            </View>
            <IconButton
              icon="close"
              size={20}
              onPress={onDismiss}
              style={{ margin: 0 }}
            />
          </View>

          <Divider />

          {/* Risk warnings */}
          {riskWarnings.length > 0 && (
            <View style={[styles.warningsContainer, { paddingHorizontal: spacing.md }]}>
              {riskWarnings.map((warning, idx) => (
                <View
                  key={idx}
                  style={[
                    styles.warningRow,
                    {
                      backgroundColor:
                        warning.level === 'error'
                          ? `${colors.error}14`
                          : `${colors.warning}14`,
                      borderRadius: borderRadius.sm,
                    },
                  ]}
                >
                  <MaterialCommunityIcons
                    name={warning.level === 'error' ? 'alert-circle-outline' : 'alert-outline'}
                    size={16}
                    color={warning.level === 'error' ? colors.error : colors.warning}
                    style={{ marginRight: 6 }}
                  />
                  <Text
                    variant="bodySmall"
                    style={{
                      color: warning.level === 'error' ? colors.error : colors.warning,
                      flex: 1,
                    }}
                  >
                    {warning.label}
                  </Text>
                </View>
              ))}
            </View>
          )}

          {/* Extraction fields */}
          <ScrollView
            style={styles.flex}
            contentContainerStyle={{ padding: spacing.md, paddingBottom: spacing.xl }}
            keyboardShouldPersistTaps="handled"
          >
            {extractedFields.length === 0 && (
              <View style={{ alignItems: 'center', paddingVertical: 16 }}>
                <MaterialCommunityIcons name="text-search" size={32} color={colors.outline} />
                <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 8, textAlign: 'center' }}>
                  {t('wizard.preview.noExtraction')}
                </Text>
              </View>
            )}
            {extractedFields.map((field) => (
              <View key={field.key} style={styles.fieldRow}>
                <Text
                  variant="labelSmall"
                  style={{
                    color: colors.onSurfaceVariant,
                    textTransform: 'capitalize',
                    marginBottom: 2,
                  }}
                >
                  {field.displayKey}
                </Text>
                {editable ? (
                  <TextInput
                    mode="outlined"
                    dense
                    value={editedValues[field.key] ?? field.value}
                    onChangeText={(v) => handleFieldChange(field.key, v)}
                    style={styles.input}
                    outlineStyle={{ borderRadius: borderRadius.sm }}
                  />
                ) : (
                  <TextInput
                    mode="outlined"
                    dense
                    value={field.value}
                    disabled
                    style={[styles.input, { backgroundColor: '#F5F5F5' }]}
                    outlineStyle={{ borderRadius: borderRadius.sm }}
                  />
                )}
              </View>
            ))}

            {/* User notes */}
            {editable && (
              <View style={[styles.fieldRow, { marginTop: spacing.sm }]}>
                <Text
                  variant="labelSmall"
                  style={{ color: colors.onSurfaceVariant, marginBottom: 2 }}
                >
                  {t('wizard.preview.notes')}
                </Text>
                <TextInput
                  mode="outlined"
                  dense
                  multiline
                  numberOfLines={2}
                  value={userNotes}
                  onChangeText={setUserNotes}
                  placeholder={t('wizard.preview.notesPlaceholder')}
                  style={styles.input}
                  outlineStyle={{ borderRadius: borderRadius.sm }}
                />
              </View>
            )}
          </ScrollView>

          {/* Action buttons */}
          <Divider />
          <View style={[styles.actions, { paddingHorizontal: spacing.md, paddingVertical: spacing.sm }]}>
            <Button
              mode="outlined"
              onPress={onDismiss}
              style={[styles.actionButton, { borderRadius: borderRadius.sm }]}
              contentStyle={styles.actionContent}
              disabled={isConfirming}
            >
              {t('wizard.preview.retry')}
            </Button>
            <Button
              mode="contained"
              onPress={handleConfirm}
              loading={isConfirming}
              disabled={isConfirming}
              style={[styles.actionButton, { borderRadius: borderRadius.sm, marginLeft: spacing.sm }]}
              contentStyle={styles.actionContent}
            >
              {t('wizard.preview.confirm')}
            </Button>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </Portal>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  modal: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    maxHeight: '85%',
  },
  flex: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
  },
  headerLeft: { flex: 1, marginRight: 8 },
  badgeRow: { flexDirection: 'row', gap: 6, marginTop: 4 },
  badge: { paddingHorizontal: 6, paddingVertical: 2 },
  warningsContainer: { paddingTop: 8, gap: 4 },
  warningRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  fieldRow: { marginBottom: 10 },
  input: { fontSize: 14 },
  actions: { flexDirection: 'row' },
  actionButton: { flex: 1 },
  actionContent: { paddingVertical: 2 },
});
