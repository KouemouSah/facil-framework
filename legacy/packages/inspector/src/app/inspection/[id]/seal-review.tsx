/**
 * Seal Review Screen — Supervisor approves/rejects seal
 */

import React, { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { extractApiError } from '@core/api/errors';
import { formatDate, formatCurrency } from '@core/utils/format';
import { LoadingScreen } from '@components/ui/loading-screen';
import { useInspectionDetail, useApproveSeal } from '@modules/inspections/services/inspections-hooks';

export default function SealReviewScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const approveMutation = useApproveSeal(id ?? '');

  const [rejectNotes, setRejectNotes] = useState('');
  const [error, setError] = useState('');

  const handleApprove = useCallback(() => {
    Alert.alert(
      t('seal.approve'),
      t('seal.impact'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('seal.approve'),
          style: 'destructive',
          onPress: async () => {
            try {
              setError('');
              await approveMutation.mutateAsync({ approved: true });
              router.back();
            } catch (err) {
              setError(extractApiError(err).message);
            }
          },
        },
      ],
    );
  }, [approveMutation, t]);

  const handleReject = useCallback(async () => {
    if (!rejectNotes.trim()) {
      setError(t('seal.rejectionReason') + ' obligatorio');
      return;
    }
    try {
      setError('');
      await approveMutation.mutateAsync({ approved: false, notes: rejectNotes.trim() });
      router.back();
    } catch (err) {
      setError(extractApiError(err).message);
    }
  }, [rejectNotes, approveMutation, t]);

  if (isLoading || !inspection) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('seal.reviewTitle')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Inspection info */}
        <View style={styles.section}>
          <Text variant="titleSmall" style={{ color: colors.onSurface }}>
            {inspection.company_name ?? '—'}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {inspection.company_nif} • {formatDate(inspection.inspection_date)}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {t('inspection.unpaidAmount')}: {formatCurrency(inspection.unpaid_obligations_amount)}
          </Text>
        </View>
        <Divider />

        {/* Seal details */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            Motivo del precinto
          </Text>
          <View style={[styles.reasonBox, { backgroundColor: `${custom.status.sealProposed}12` }]}>
            <MaterialCommunityIcons name="lock-alert" size={20} color={custom.status.sealProposed as string} />
            <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1, marginLeft: 8 }}>
              {inspection.seal_reason ? t(`seal.reasons.${inspection.seal_reason}`) : inspection.seal_reason}
            </Text>
          </View>
          {inspection.seal_notes && (
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 8 }}>
              Notas: {inspection.seal_notes}
            </Text>
          )}
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 4 }}>
            Propuesto por: {inspection.agent_name} • {inspection.seal_proposed_at ? formatDate(inspection.seal_proposed_at, 'dd/MM/yyyy HH:mm') : ''}
          </Text>
        </View>
        <Divider />

        {/* Reject notes */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('seal.rejectionReason')} (si rechaza)
          </Text>
          <TextInput
            mode="flat"
            value={rejectNotes}
            onChangeText={setRejectNotes}
            multiline
            numberOfLines={3}
            maxLength={2000}
            placeholder="Motivo del rechazo..."
            style={{ backgroundColor: 'transparent' }}
          />
        </View>

        {error ? (
          <Text variant="bodyMedium" style={{ color: colors.error, paddingHorizontal: 16 }}>{error}</Text>
        ) : null}

        {/* Action buttons */}
        <View style={styles.actions}>
          <Button
            mode="contained"
            icon="check"
            onPress={handleApprove}
            loading={approveMutation.isPending}
            disabled={approveMutation.isPending}
            buttonColor={custom.status.sealApproved as string}
            style={[styles.actionButton, { flex: 1 }]}
          >
            {t('seal.approve')}
          </Button>
          <Button
            mode="outlined"
            icon="close"
            onPress={handleReject}
            loading={approveMutation.isPending}
            disabled={approveMutation.isPending}
            textColor={colors.onSurface}
            style={[styles.actionButton, { flex: 1 }]}
          >
            {t('seal.reject')}
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
  reasonBox: { flexDirection: 'row', alignItems: 'center', padding: 12, borderRadius: 8 },
  actions: { flexDirection: 'row', gap: 12, paddingHorizontal: 16, paddingTop: 16 },
  actionButton: { borderRadius: 8 },
});
