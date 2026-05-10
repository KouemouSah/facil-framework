/**
 * Request Detail Screen — Native Android v2
 *
 * Minimal, scannable layout:
 * - Hero: avatar + title + status + progress
 * - Payment card (prominent if exists)
 * - Quick info: entity + appointment
 * - Essential summary: max 5 fields (rest in PDF)
 * - Documents
 * - PDF download sticky button
 */

import { useState, useMemo, useCallback } from 'react';
import {
  StyleSheet,
  View,
  ScrollView,
  Image,
  Pressable,
  Modal,
} from 'react-native';
import {
  Text,
  Button,
  Divider,
  ActivityIndicator,
  ProgressBar,
  IconButton,
  Snackbar,
} from 'react-native-paper';
import { documentDirectory, downloadAsync } from 'expo-file-system/legacy';
import { shareAsync } from 'expo-sharing';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useScreenProtection } from '@core/security/use-screen-protection';
import { formatCurrency, formatDate } from '@core/utils/format';
import { appConfig } from '@core/config/app';
import { getAccessToken } from '@core/auth/auth-storage';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { useRequestDetailView } from '@modules/service-requests';
import { RequestStatusBadge } from '@modules/service-requests/components/request-status-badge';
import { BundleDetailSection } from '@modules/service-requests/components/bundle-detail-section';
import type { DataSection } from '@modules/service-requests';
import { RetryPaymentSheet } from '@modules/payments';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function humanizeCode(code: string): string {
  return code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function getDocIcon(name: string): string {
  const lower = name.toLowerCase();
  if (lower.includes('photo') || lower.includes('foto')) return 'camera';
  if (lower.includes('pasaporte')) return 'passport';
  if (lower.includes('dip') || lower.includes('dni')) return 'card-account-details';
  return 'file-document-outline';
}

/**
 * Extract only essential fields from data sections.
 * On mobile we show max 5-6 key fields. The rest is in the PDF.
 */
function extractEssentialFields(
  sections: DataSection[],
): { label: string; value: string }[] {
  const essentialKeys = [
    'nombre', 'apellido', 'nom', 'name',
    'numero', 'dip', 'dni', 'nif', 'pasaporte',
    'tipo', 'type', 'motivo',
    'fecha_nacimiento', 'date_naissance', 'nacionalidad',
    'sexo', 'genero',
  ];

  const result: { label: string; value: string }[] = [];

  for (const section of sections) {
    for (const field of section.fields) {
      if (!field.value) continue;
      const lowerLabel = field.label.toLowerCase().replace(/\s/g, '_');
      const isEssential = essentialKeys.some((k) => lowerLabel.includes(k));
      if (isEssential && result.length < 6) {
        result.push({ label: field.label, value: field.value });
      }
    }
  }

  // If we found fewer than 3, just take the first fields from the first section
  if (result.length < 3) {
    for (const section of sections) {
      for (const field of section.fields) {
        if (!field.value && result.length >= 3) continue;
        if (field.value && !result.find((r) => r.label === field.label)) {
          result.push({ label: field.label, value: field.value });
          if (result.length >= 5) return result;
        }
      }
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function RequestDetailScreen() {
  useScreenProtection();
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const { data, isLoading, isError, refetch } = useRequestDetailView(id ?? '');
  const [photoModalVisible, setPhotoModalVisible] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [lastDownloadedUri, setLastDownloadedUri] = useState<{ uri: string; mime: string } | null>(null);
  const [retryVisible, setRetryVisible] = useState(false);

  /** Get MIME type from file extension */
  const getMimeType = (fileName: string): string => {
    const ext = fileName.split('.').pop()?.toLowerCase() ?? '';
    if (ext === 'pdf') return 'application/pdf';
    if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
    if (ext === 'png') return 'image/png';
    return 'application/octet-stream';
  };

  /** Download file to persistent storage + show snackbar with "Ouvrir" */
  const downloadFile = useCallback(async (url: string, fileName: string, headers?: Record<string, string>) => {
    setIsDownloading(true);
    setLastDownloadedUri(null);
    try {
      const fileUri = `${documentDirectory}${fileName}`;
      const download = await downloadAsync(url, fileUri, headers ? { headers } : undefined);

      if (download.status === 200) {
        const mime = getMimeType(fileName);
        setLastDownloadedUri({ uri: download.uri, mime });
        setSnackbar(t('detail.downloadComplete'));
      } else {
        setSnackbar(t('common.error'));
      }
    } catch {
      setSnackbar(t('common.error'));
    } finally {
      setIsDownloading(false);
    }
  }, [t]);

  /** Open last downloaded file via share sheet */
  const handleOpenFile = useCallback(async () => {
    if (!lastDownloadedUri) return;
    try {
      await shareAsync(lastDownloadedUri.uri, {
        mimeType: lastDownloadedUri.mime,
        dialogTitle: t('detail.openFile'),
      });
    } catch {
      // User cancelled share sheet — ignore
    }
  }, [lastDownloadedUri, t]);

  const handleDownloadPDF = useCallback(async () => {
    if (!id) return;
    const token = await getAccessToken();
    const url = `${appConfig.api.baseUrl}/api/${appConfig.api.version}${API_ENDPOINTS.serviceRequests.summaryPdf(id)}?language=es`;
    await downloadFile(url, `solicitud-${id.slice(0, 8)}.pdf`, { Authorization: `Bearer ${token}` });
  }, [id, downloadFile]);

  const handleDownloadDocument = useCallback(async (fileUrl: string | undefined, fileName: string) => {
    if (!fileUrl) {
      setSnackbar(t('common.error'));
      return;
    }
    await downloadFile(fileUrl, fileName);
  }, [downloadFile, t]);

  const essentialFields = useMemo(
    () => (data ? extractEssentialFields(data.data_sections) : []),
    [data],
  );

  if (isLoading) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <ActivityIndicator size="large" color={colors.primary} />
      </SafeAreaView>
    );
  }

  if (isError || !data) {
    return (
      <SafeAreaView style={[styles.container, styles.centered, { backgroundColor: colors.background }]} edges={['top']}>
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>{t('common.error')}</Text>
        <Button mode="outlined" onPress={() => router.back()} style={{ marginTop: 12 }}>{t('common.back')}</Button>
      </SafeAreaView>
    );
  }

  const {
    request, stepper_phases, current_phase_index, photo_url,
    tariff, appointment, documents, workflow_name_es,
    solicitud_type_display, payment_status, payment_reference, receipt_number,
    bundle_details,
  } = data;
  const isBundle = request.workflow_code === 'BUNDLE_PAYMENT' && !!bundle_details;

  // Retry CTA visible when a payment attempt failed/was cancelled, or when the
  // SR is sitting in `pending_payment` (typical after the first wizard pass
  // when the citizen abandoned the BANGE redirect or chose cash and the agent
  // hasn't validated yet — they may want to switch method).
  const canRetryPayment =
    payment_status === 'failed' ||
    payment_status === 'cancelled' ||
    (payment_status == null && request.status === 'pending_payment');

  const progress = stepper_phases.length > 0
    ? (current_phase_index + 1) / stepper_phases.length
    : 0;
  const currentPhaseName = stepper_phases[current_phase_index]?.title_es ?? '';
  const totalSections = data.data_sections.reduce((sum, s) => sum + s.fields.length, 0);

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* Top bar */}
      <View style={[styles.topBar, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <IconButton icon="arrow-left" size={24} onPress={() => router.back()} />
        <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }} numberOfLines={1}>
          {t('requests.detail')}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 80 }} showsVerticalScrollIndicator={false}>

        {/* ═══ HERO ═══ */}
        <View style={[styles.hero, { padding: spacing.md, backgroundColor: colors.surface }]}>
          <View style={styles.heroRow}>
            {photo_url ? (
              <Pressable onPress={() => setPhotoModalVisible(true)}>
                <Image source={{ uri: photo_url }} style={styles.photoSquare} />
              </Pressable>
            ) : (
              <View style={[styles.photoPlaceholder, { backgroundColor: colors.primaryContainer }]}>
                <MaterialCommunityIcons name="file-document" size={28} color={colors.primary} />
              </View>
            )}
            <View style={styles.heroText}>
              <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700' }} numberOfLines={2}>
                {workflow_name_es}
              </Text>
              <Text variant="bodySmall" style={{ color: colors.outline }}>
                {request.reference}{solicitud_type_display ? ` · ${solicitud_type_display}` : ''}
              </Text>
              <View style={{ marginTop: 4 }}>
                <RequestStatusBadge status={request.status} />
              </View>
            </View>
          </View>

          {stepper_phases.length > 0 && (
            <View style={{ marginTop: 12 }}>
              <View style={styles.progressHeader}>
                <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>{currentPhaseName}</Text>
                <Text variant="labelSmall" style={{ color: colors.primary, fontWeight: '600' }}>
                  {current_phase_index + 1}/{stepper_phases.length}
                </Text>
              </View>
              <ProgressBar progress={progress} color={colors.primary} style={styles.progressBar} />
            </View>
          )}
        </View>

        {/* ═══ PAYMENT (prominent, left-aligned) ═══ */}
        {payment_status && (
          <>
            <Divider />
            <View style={{ paddingHorizontal: spacing.md, paddingVertical: 12, backgroundColor: colors.surface }}>
              {/* Line 1: icon + Paiement | badge | date | amount */}
              <View style={styles.payTitleRow}>
                <MaterialCommunityIcons name="credit-card-check-outline" size={18} color={colors.primary} />
                <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginLeft: 6 }}>
                  {t('requests.payment')}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.outline, marginHorizontal: 6 }}>|</Text>
                <RequestStatusBadge status={payment_status} compact />
                {request.updated_at && (
                  <>
                    <Text variant="bodySmall" style={{ color: colors.outline, marginHorizontal: 6 }}>|</Text>
                    <Text variant="labelSmall" style={{ color: colors.outline }}>
                      {formatDate(request.updated_at, 'dd/MM/yyyy')}
                    </Text>
                  </>
                )}
                {tariff && (
                  <>
                    <Text variant="bodySmall" style={{ color: colors.outline, marginHorizontal: 6 }}>|</Text>
                    <Text style={{ color: colors.primary, fontWeight: '700', fontSize: 14 }}>
                      {formatCurrency(tariff.total_amount, tariff.currency)}
                    </Text>
                  </>
                )}
              </View>

              {/* Line 3-4: References left-aligned, label + value on same row */}
              <View style={{ marginTop: 8, gap: 4 }}>
                {payment_reference && (
                  <View style={styles.refRow}>
                    <Text variant="labelSmall" style={styles.refLabel}>{t('detail.paymentReference')}</Text>
                    <Text variant="bodySmall" style={{ color: colors.onSurface, flex: 1 }} numberOfLines={1}>{payment_reference}</Text>
                  </View>
                )}
                {receipt_number && (
                  <View style={styles.refRow}>
                    <Text variant="labelSmall" style={styles.refLabel}>{t('detail.receiptNumber')}</Text>
                    <Text variant="bodySmall" style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}>{receipt_number}</Text>
                  </View>
                )}
              </View>

              {canRetryPayment && (
                <Button
                  mode="contained-tonal"
                  icon="refresh"
                  onPress={() => setRetryVisible(true)}
                  style={{ marginTop: 12, alignSelf: 'flex-start' }}
                  compact
                >
                  {t('payments.retry.cta')}
                </Button>
              )}
            </View>
          </>
        )}

        {/* ═══ RENDEZ-VOUS (compact row, blue background) ═══ */}
        {(appointment || request.cita_date) && (() => {
          const rdvDate = appointment?.date ?? request.cita_date;
          const rdvTime = appointment?.time ?? request.cita_time;
          const rdvLocation = appointment?.location ?? request.cita_location;
          return (
            <>
              <Divider />
              <View style={[styles.appointmentBlock, { paddingHorizontal: spacing.md, paddingVertical: 10 }]}>
                <View style={styles.appointmentRow}>
                  <MaterialCommunityIcons name="calendar-clock" size={18} color="#1565C0" />
                  <Text variant="bodyMedium" style={{ color: '#0D47A1', fontWeight: '700', marginLeft: 6 }}>
                    {rdvDate ? formatDate(rdvDate, 'dd/MM/yyyy') : ''}
                    {rdvTime ? ` · ${rdvTime}` : ''}
                  </Text>
                  {rdvLocation && (
                    <>
                      <Text style={{ color: '#90CAF9', marginHorizontal: 6 }}>|</Text>
                      <MaterialCommunityIcons name="map-marker" size={14} color="#1565C0" />
                      <Text variant="bodyMedium" style={{ color: '#0D47A1', fontWeight: '600', marginLeft: 2 }}>
                        {rdvLocation}
                      </Text>
                    </>
                  )}
                </View>
              </View>
            </>
          );
        })()}

        {/* ═══ QUICK INFO (entity) ═══ */}
        {request.entity_code && (
          <View style={[styles.entityRow, { paddingHorizontal: spacing.md, paddingVertical: 8, backgroundColor: colors.surfaceVariant }]}>
            <MaterialCommunityIcons name="domain" size={16} color={colors.onSurfaceVariant} />
            <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, marginLeft: 4 }}>
              {humanizeCode(request.entity_code)}
            </Text>
          </View>
        )}

        {/* ═══ BUNDLE DETAIL (parity with web /service-requests/[id]) ═══
            Three-card KPI row + per-entity split cards + paid/pending
            obligation lists. Replaces the generic "summary" block for
            BUNDLE_PAYMENT requests where the breakdown is the actual
            content. See debug/tesoro/s.png. */}
        {isBundle && bundle_details ? (
          <>
            <Divider />
            <BundleDetailSection details={bundle_details} />
          </>
        ) : null}

        {/* ═══ ESSENTIAL SUMMARY (max 5-6 fields) ═══ */}
        {!isBundle && essentialFields.length > 0 && (
          <View style={{ paddingHorizontal: spacing.md, paddingTop: spacing.md }}>
            <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 8 }}>
              {t('detail.summary')}
            </Text>
            {essentialFields.map((field, i) => (
              <View key={i}>
                {i > 0 && <Divider style={{ marginVertical: 1 }} />}
                <View style={styles.fieldRow}>
                  <Text variant="bodySmall" style={{ color: colors.outline, flex: 1 }}>{field.label}</Text>
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1.5, textAlign: 'right', fontWeight: '500' }} numberOfLines={1}>
                    {field.value}
                  </Text>
                </View>
              </View>
            ))}
            {totalSections > essentialFields.length && (
              <Text variant="labelSmall" style={{ color: colors.outline, marginTop: 6, fontStyle: 'italic' }}>
                {t('detail.moreInPDF', { count: totalSections - essentialFields.length })}
              </Text>
            )}
          </View>
        )}

        {/* ═══ DOCUMENTS ═══ */}
        {documents.length > 0 && (
          <View style={{ paddingHorizontal: spacing.md, paddingTop: spacing.lg }}>
            <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginBottom: 8 }}>
              {t('requests.documents')} ({documents.length})
            </Text>
            {documents.map((doc, i) => (
              <View key={doc.id}>
                {i > 0 && <Divider />}
                <Pressable
                  style={styles.docRow}
                  android_ripple={{ color: colors.primaryContainer }}
                  onPress={() => handleDownloadDocument(doc.file_url, doc.file_name)}
                >
                  <MaterialCommunityIcons
                    name={getDocIcon(doc.document_name) as keyof typeof MaterialCommunityIcons.glyphMap}
                    size={20}
                    color={colors.primary}
                  />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text variant="bodyMedium" style={{ color: colors.onSurface }} numberOfLines={1}>
                      {humanizeCode(doc.document_name)}
                    </Text>
                    <Text variant="bodySmall" style={{ color: colors.outline }} numberOfLines={1}>
                      {doc.file_name}
                    </Text>
                  </View>
                  <MaterialCommunityIcons name="download" size={20} color={colors.outline} />
                </Pressable>
              </View>
            ))}
          </View>
        )}

      </ScrollView>

      {/* ═══ STICKY BOTTOM ═══ */}
      <View style={[styles.bottomBar, { backgroundColor: colors.surface, borderTopColor: colors.outlineVariant }]}>
        <Button
          mode="contained"
          icon="file-pdf-box"
          onPress={handleDownloadPDF}
          loading={isDownloading}
          disabled={isDownloading}
          style={{ flex: 1, borderRadius: borderRadius.sm }}
          contentStyle={{ paddingVertical: 4 }}
        >
          {t('detail.downloadPDF')}
        </Button>
      </View>

      {/* ═══ PHOTO MODAL ═══ */}
      {photo_url && (
        <Modal visible={photoModalVisible} transparent animationType="fade" onRequestClose={() => setPhotoModalVisible(false)}>
          <Pressable style={styles.modalOverlay} onPress={() => setPhotoModalVisible(false)}>
            <Image source={{ uri: photo_url }} style={styles.modalPhoto} resizeMode="contain" />
            <IconButton icon="close" iconColor="#fff" size={28} style={styles.modalClose} onPress={() => setPhotoModalVisible(false)} />
          </Pressable>
        </Modal>
      )}

      <Snackbar
        visible={!!snackbar}
        onDismiss={() => { setSnackbar(null); setLastDownloadedUri(null); }}
        duration={5000}
        action={lastDownloadedUri ? { label: t('detail.openFile'), onPress: handleOpenFile } : undefined}
      >
        {snackbar ?? ''}
      </Snackbar>

      {id ? (
        <RetryPaymentSheet
          visible={retryVisible}
          onDismiss={() => setRetryVisible(false)}
          serviceRequestId={id}
          onResult={(outcome) => {
            if (outcome.kind === 'redirect') {
              setSnackbar(t('payments.retry.redirecting'));
              // Refresh detail view shortly after — backend will have updated
              // payment_status to 'processing'.
              setTimeout(() => { void refetch(); }, 2500);
            } else if (outcome.kind === 'agent_validation') {
              const messageKey =
                outcome.messageKey === 'cash' ? 'payments.retry.cashPending'
                : outcome.messageKey === 'check' ? 'payments.retry.checkPending'
                : 'payments.retry.agentPending';
              setSnackbar(t(messageKey));
              void refetch();
            } else {
              setSnackbar(outcome.message);
            }
          }}
        />
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  centered: { justifyContent: 'center', alignItems: 'center' },
  topBar: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1 },
  hero: {},
  heroRow: { flexDirection: 'row', alignItems: 'center' },
  photoSquare: { width: 72, height: 72, borderRadius: 12, marginRight: 14 },
  photoPlaceholder: { width: 72, height: 72, borderRadius: 12, marginRight: 14, justifyContent: 'center', alignItems: 'center' },
  heroText: { flex: 1 },
  progressHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  progressBar: { height: 6, borderRadius: 3 },
  payTitleRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  refRow: { flexDirection: 'row', alignItems: 'baseline' },
  refLabel: { color: '#757575', width: 100, marginRight: 8 },
  appointmentBlock: { backgroundColor: '#E3F2FD' },
  appointmentRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  entityRow: { flexDirection: 'row', alignItems: 'center' },
  fieldRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8 },
  docRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12 },
  bottomBar: { position: 'absolute', bottom: 0, left: 0, right: 0, padding: 12, borderTopWidth: 1 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.9)', justifyContent: 'center', alignItems: 'center' },
  modalPhoto: { width: '90%', height: '70%' },
  modalClose: { position: 'absolute', top: 40, right: 16 },
});
