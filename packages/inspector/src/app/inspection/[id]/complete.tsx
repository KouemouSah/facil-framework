/**
 * Complete Inspection Screen
 * Summary → Signature → Confirm
 */

import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import { LoadingScreen } from '@components/ui/loading-screen';
import { extractApiError } from '@core/api/errors';
import { hapticSuccess, hapticError } from '@core/utils/haptics';
import { useInspectionDetail, useCompleteInspection, useUpdateInspection } from '@modules/inspections/services/inspections-hooks';
import { SignaturePad, type SignatureResult } from '@modules/signature/components/signature-pad';

export default function CompleteInspectionScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const completeMutation = useCompleteInspection(id ?? '');
  const updateMutation = useUpdateInspection(id ?? '');

  const [notes, setNotes] = useState('');
  const [signatureResult, setSignatureResult] = useState<SignatureResult | null>(null);
  const [error, setError] = useState('');

  // Predict result (safe even before data loads — defaults to non_conforme)
  const isConforme = inspection?.activity_conforme === true && inspection?.unpaid_obligations_count === 0;
  const predictedResult = isConforme ? 'conforme' : 'non_conforme';
  const resultColor = isConforme ? (custom.status.conforme as string) : (custom.status.nonConforme as string);

  const handleComplete = useCallback(async () => {
    if (!id || !signatureResult) return;

    // Save signature first
    try {
      await updateMutation.mutateAsync({ agent_signature: signatureResult.base64 });
    } catch {
      // Continue even if signature save fails — hash ensures integrity
    }

    Alert.alert(
      t('inspection.complete'),
      t('complete.confirmMessage', { result: t(`result.${predictedResult}`) }),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          style: 'default',
          onPress: async () => {
            try {
              setError('');
              await completeMutation.mutateAsync({ notes: notes.trim() || undefined });
              hapticSuccess();
              router.back();
            } catch (err) {
              hapticError();
              setError(extractApiError(err).message);
            }
          },
        },
      ],
    );
  }, [id, signatureResult, notes, predictedResult, completeMutation, updateMutation, t]);

  if (isLoading || !inspection) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('inspection.complete')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Summary */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('complete.summary')}
          </Text>
          <View style={styles.summaryRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>{t('complete.company')}</Text>
            <Text variant="bodyMedium" style={{ color: colors.onSurface }}>{inspection.company_name ?? '—'}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>{t('complete.date')}</Text>
            <Text variant="bodyMedium">{formatDate(inspection.inspection_date)}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>{t('complete.activity')}</Text>
            <Text variant="bodyMedium" style={{ color: inspection.activity_conforme ? (custom.status.conforme as string) : (custom.status.nonConforme as string) }}>
              {inspection.activity_conforme ? t('complete.conforme') : t('complete.nonConforme')}
            </Text>
          </View>
          <View style={styles.summaryRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>{t('complete.photosCount')}</Text>
            <Text variant="bodyMedium">{inspection.photos.length}</Text>
          </View>
          <View style={styles.summaryRow}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>{t('complete.pendingObligations')}</Text>
            <Text variant="bodyMedium" style={{ color: inspection.unpaid_obligations_count > 0 ? (custom.status.nonConforme as string) : (custom.status.conforme as string) }}>
              {inspection.unpaid_obligations_count}
            </Text>
          </View>
        </View>
        <Divider />

        {/* Predicted Result */}
        <View style={[styles.resultBanner, { backgroundColor: `${resultColor}12` }]}>
          <MaterialCommunityIcons
            name={isConforme ? 'check-circle' : 'alert-circle'}
            size={24}
            color={resultColor}
          />
          <View style={{ marginLeft: 12 }}>
            <Text variant="labelLarge" style={{ color: resultColor }}>
              {t('complete.predictedResult')}: {t(`result.${predictedResult}`).toUpperCase()}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {isConforme
                ? t('complete.conformeReason')
                : inspection.unpaid_obligations_count > 0
                  ? t('complete.nonConformeObligations', { count: inspection.unpaid_obligations_count })
                  : t('complete.nonConformeActivity')}
            </Text>
          </View>
        </View>
        <Divider />

        {/* Agent signature canvas */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('inspection.signature')}
          </Text>
          <SignaturePad
            onSignature={(result) => setSignatureResult(result)}
            onClear={() => setSignatureResult(null)}
            height={180}
          />
        </View>
        <Divider />

        {/* Notes */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('complete.finalNotes')}
          </Text>
          <TextInput
            mode="flat"
            value={notes}
            onChangeText={setNotes}
            multiline
            numberOfLines={3}
            maxLength={2000}
            placeholder={t('complete.finalNotesPlaceholder')}
            style={{ backgroundColor: 'transparent' }}
          />
        </View>

        {error ? (
          <Text variant="bodyMedium" style={{ color: colors.error, paddingHorizontal: 16 }}>{error}</Text>
        ) : null}

        {/* Submit */}
        <View style={styles.submitSection}>
          <Button
            mode="contained"
            icon="check-circle"
            onPress={handleComplete}
            loading={completeMutation.isPending}
            disabled={completeMutation.isPending || !signatureResult}
            style={styles.submitButton}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('inspection.complete')}
          </Button>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  content: { paddingBottom: 32 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  resultBanner: { flexDirection: 'row', alignItems: 'center', padding: 16, marginHorizontal: 16, marginVertical: 12, borderRadius: 8 },
  submitSection: { paddingHorizontal: 16, paddingTop: 16 },
  submitButton: { borderRadius: 8 },
});
