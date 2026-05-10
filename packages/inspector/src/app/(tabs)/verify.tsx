/**
 * Verify License Screen
 *
 * Search by NIF (GExxxxx) or N Registro (PE-xxxxxx).
 * Shows company details, obligations, inspection history.
 * Button to start inspection from verified license.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Modal, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, HelperText, Snackbar, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { extractApiError } from '@core/api/errors';
import { formatCurrency, formatDate } from '@core/utils/format';
import { StatusBadge } from '@components/ui/status-badge';
import { QRScanner } from '@modules/scanner/components/qr-scanner';
import { parseLicenseQR } from '@modules/scanner/services/qr-parser';
import { useQRVerification } from '@modules/scanner/services/scanner-hooks';
import type { LicenseVerification, LicenseObligation } from '@modules/inspections/types/inspection.types';

export default function VerifyScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const { agentContext } = useAuth();
  const insets = useSafeAreaInsets();

  const [identifier, setIdentifier] = useState('');
  const [error, setError] = useState('');
  const { openScanner } = useLocalSearchParams<{ openScanner?: string }>();
  const [showScanner, setShowScanner] = useState(false);
  const [snackMessage, setSnackMessage] = useState('');

  // Auto-open scanner when navigated with openScanner=1 (from dashboard quick action)
  useEffect(() => {
    if (openScanner === '1') {
      setShowScanner(true);
    }
  }, [openScanner]);

  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState<LicenseVerification | null>(null);

  const qrVerification = useQRVerification();

  const doSearch = useCallback(async () => {
    const trimmed = identifier.trim();
    if (!trimmed || trimmed.length < 3) return;
    setError('');
    setResult(null);
    setIsSearching(true);

    try {
      const { verificationApi } = await import('@modules/verification/services/verification-api');
      const data = await verificationApi.verifyByIdentifier(trimmed);
      setResult(data);
    } catch (err) {
      const apiError = extractApiError(err);
      if (apiError.status === 404) {
        setError(t('verify.notFound'));
      } else {
        setError(apiError.message);
      }
    } finally {
      setIsSearching(false);
    }
  }, [identifier, t]);

  const handleQRScan = useCallback(async (data: string) => {
    setShowScanner(false);
    const qrData = parseLicenseQR(data);
    if (!qrData) {
      setSnackMessage(t('scanner.invalidQR'));
      return;
    }

    setError('');
    setIsSearching(true);
    try {
      const verification = await qrVerification.mutateAsync(qrData);
      setResult(verification);
      setIdentifier(verification.company_nif ?? qrData.licenseRef);
    } catch (err) {
      const apiError = extractApiError(err);
      if (apiError.status === 404) {
        setError(t('verify.notFound'));
      } else {
        setError(apiError.message);
      }
    } finally {
      setIsSearching(false);
    }
  }, [qrVerification, t]);

  const handleStartInspection = useCallback(() => {
    if (!result) return;
    router.push({
      pathname: '/inspection/create' as never,
      params: {
        license_id: result.license_id,
        company_id: result.company_id,
        company_name: result.company_name ?? '',
      },
    });
  }, [result]);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text variant="headlineSmall" style={{ color: colors.primary, fontWeight: '700' }}>
          {t('verify.title')}
        </Text>
      </View>

      {/* QR Scanner Button */}
      <View style={styles.qrSection}>
        <Button
          mode="contained-tonal"
          icon="qrcode-scan"
          onPress={() => setShowScanner(true)}
          style={styles.qrButton}
          contentStyle={{ paddingVertical: 8 }}
        >
          {t('scanner.scanLicense')}
        </Button>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 6 }}>
          {t('scanner.orManual')}
        </Text>
      </View>

      {/* Search Bar */}
      <View style={styles.searchBar}>
        <TextInput
          mode="outlined"
          value={identifier}
          onChangeText={setIdentifier}
          placeholder={t('verify.searchPlaceholder')}
          left={<TextInput.Icon icon="magnify" />}
          right={
            identifier
              ? <TextInput.Icon icon="close" onPress={() => { setIdentifier(''); setResult(null); setError(''); }} />
              : undefined
          }
          onSubmitEditing={doSearch}
          returnKeyType="search"
          autoCapitalize="characters"
          disabled={isSearching}
          style={styles.searchInput}
        />
        <Button
          mode="contained"
          onPress={doSearch}
          loading={isSearching}
          disabled={isSearching || identifier.trim().length < 3}
          style={styles.searchButton}
          compact
        >
          {t('verify.search')}
        </Button>
      </View>

      {error ? <HelperText type="error" style={styles.error}>{error}</HelperText> : null}

      {/* Results */}
      {result && (
        <ScrollView contentContainerStyle={styles.results}>
          {/* Company Header */}
          <View style={[styles.companyHeader, { backgroundColor: colors.surface }]}>
            <Text variant="titleMedium" style={{ color: colors.onSurface }}>
              {result.company_name ?? '-'}
            </Text>
            <View style={styles.companyMeta}>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {result.company_nif ?? result.company_registration_number ?? '-'}
              </Text>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {result.forma_juridica} {result.commerce_type ? `\u2022 ${result.commerce_type}` : ''}
              </Text>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {result.city_name} {result.zone_code ? `\u2022 Zone ${result.zone_code}` : ''}
              </Text>
            </View>
            <Divider style={{ marginVertical: 8 }} />
            <View style={styles.companyStats}>
              <View style={styles.statCol}>
                <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
                  {t('verify.fiscalYear')}
                </Text>
                <Text variant="titleSmall" style={{ color: colors.onSurface }}>
                  {result.fiscal_year}
                </Text>
              </View>
              <View style={styles.statCol}>
                <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
                  {t('verify.licenseStatus')}
                </Text>
                <StatusBadge status={result.license_status} label={result.license_status} size="medium" />
              </View>
              <View style={styles.statCol}>
                <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
                  {t('inspection.unpaidAmount')}
                </Text>
                <Text
                  variant="titleSmall"
                  style={{
                    color: result.total_amount - result.amount_paid > 0
                      ? custom.status.nonConforme
                      : custom.status.conforme,
                  }}
                >
                  {formatCurrency(result.total_amount - result.amount_paid)}
                </Text>
              </View>
            </View>
          </View>

          {/* Agent scope context badge */}
          {result.agent_scope && agentContext && (
            <View style={[styles.scopeBadge, { backgroundColor: `${colors.primary}10` }]}>
              <MaterialCommunityIcons name="shield-account" size={18} color={colors.primary} />
              <Text variant="bodySmall" style={{ color: colors.primary, marginLeft: 6, flex: 1 }}>
                {t('verify.agentScope', { defaultValue: 'Scope' })}:{' '}
                {result.agent_scope.allowed_fee_types?.join(', ') ?? 'N/A'}
                {result.agent_scope.required_ministry_id ? ` (${t('verify.ministryScoped', { defaultValue: 'min. specific' })})` : ''}
                {' \u2022 '}{agentContext.locationCity}
              </Text>
            </View>
          )}

          {/* P4: Existing dossier banner (info blue) */}
          {result.existing_dossier && (
            <View style={[styles.infoBanner, { backgroundColor: `${colors.primary}15` }]}>
              <MaterialCommunityIcons name="folder-open" size={20} color={colors.primary} />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text variant="labelMedium" style={{ color: colors.primary }}>
                  {t('verify.existingDossier')}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                  {result.existing_dossier.reference} • {result.existing_dossier.source}
                  {' • '}{formatDate(result.existing_dossier.created_at)}
                </Text>
              </View>
            </View>
          )}

          {/* P4: Pending citizen payment warning (orange) */}
          {result.has_pending_citizen_payment && result.pending_payment_info && (
            <View style={[styles.warningBanner, { backgroundColor: `${custom.status.miseEnDemeure}15` }]}>
              <MaterialCommunityIcons name="clock-alert" size={20} color={custom.status.miseEnDemeure} />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text variant="labelMedium" style={{ color: custom.status.miseEnDemeure }}>
                  {t('verify.pendingPayment')}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                  {result.pending_payment_info.payment_reference}
                  {result.pending_payment_info.total_amount !== null
                    ? ` • ${formatCurrency(result.pending_payment_info.total_amount)}`
                    : ''}
                  {' • '}{result.pending_payment_info.workflow_status}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 2 }}>
                  {t('verify.pendingPaymentHint')}
                </Text>
              </View>
            </View>
          )}

          {/* Obligations */}
          {result.obligations.length > 0 && (
            <View style={styles.section}>
              <View style={styles.obligationsHeader}>
                <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
                  {t('inspection.obligations')} ({result.obligations.length})
                </Text>
                {/* P4: collectible badge */}
                {result.restricted_obligations !== undefined && (() => {
                  const collectible = result.obligations.length - (result.restricted_obligations?.length ?? 0);
                  return (
                    <Text
                      variant="bodySmall"
                      style={{
                        color: result.agent_can_collect_all
                          ? custom.status.conforme
                          : custom.status.miseEnDemeure,
                        fontWeight: '600',
                      }}
                    >
                      {collectible}/{result.obligations.length} {t('verify.collectible')}
                    </Text>
                  );
                })()}
              </View>
              {result.obligations.map((ob: LicenseObligation, i: number) => {
                const restricted = ob.agent_restricted === true;
                return (
                  <React.Fragment key={ob.id}>
                    <View style={[styles.obligationItem, restricted && styles.obligationRestricted]}>
                      <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>
                        {restricted && (
                          <MaterialCommunityIcons
                            name="lock"
                            size={16}
                            color={colors.onSurfaceVariant}
                            style={{ marginRight: 6 }}
                          />
                        )}
                        <View style={{ flex: 1 }}>
                          <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                            {ob.service_name ?? ob.fee_type}
                          </Text>
                          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                            {ob.ministry_name} {ob.due_date ? `\u2022 ${t('obligations.dueDate')}: ${formatDate(ob.due_date)}` : ''}
                          </Text>
                          {restricted && ob.agent_restricted_reason && (
                            <Text variant="bodySmall" style={{ color: custom.status.miseEnDemeure, marginTop: 2 }}>
                              {t('verify.outOfScope')}
                            </Text>
                          )}
                        </View>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text
                          variant="titleSmall"
                          style={{
                            color: ob.status === 'paid'
                              ? custom.status.conforme
                              : custom.status.nonConforme,
                          }}
                        >
                          {formatCurrency(ob.amount + (ob.penalty_amount ?? 0))}
                        </Text>
                        <StatusBadge
                          status={ob.status === 'paid' ? 'completed' : 'in_progress'}
                          label={ob.status}
                        />
                      </View>
                    </View>
                    {i < result.obligations.length - 1 && <Divider style={{ marginLeft: 16 }} />}
                  </React.Fragment>
                );
              })}
              {/* P4: Footer info if agent cannot collect all */}
              {result.agent_can_collect_all === false && (
                <Text
                  variant="bodySmall"
                  style={{
                    color: colors.onSurfaceVariant,
                    marginTop: 8,
                    fontStyle: 'italic',
                    paddingHorizontal: 4,
                  }}
                >
                  {t('verify.restrictedHint')}
                </Text>
              )}
            </View>
          )}

          {/* Active MED Warning */}
          {result.active_mise_en_demeure && (
            <View style={[styles.medWarning, { backgroundColor: `${custom.status.miseEnDemeure}15` }]}>
              <MaterialCommunityIcons name="alert" size={20} color={custom.status.miseEnDemeure} />
              <View style={{ flex: 1, marginLeft: 8 }}>
                <Text variant="labelMedium" style={{ color: custom.status.miseEnDemeure }}>
                  {t('verify.activeMed')}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                  Limite: {formatDate(result.active_mise_en_demeure.mise_en_demeure_deadline, 'dd/MM/yyyy HH:mm')}
                </Text>
              </View>
            </View>
          )}

          {/* Previous Inspections */}
          {result.previous_inspections.length > 0 && (
            <View style={styles.section}>
              <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
                {t('verify.previousInspections')} ({result.previous_inspections.length})
              </Text>
              {result.previous_inspections.slice(0, 5).map((insp, i) => (
                <React.Fragment key={insp.id}>
                  <View style={styles.prevItem}>
                    <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
                      {formatDate(insp.inspection_date)}
                    </Text>
                    <StatusBadge
                      status={insp.result ?? insp.status}
                      label={insp.result ?? insp.status}
                    />
                  </View>
                  {i < Math.min(result.previous_inspections.length, 5) - 1 && <Divider />}
                </React.Fragment>
              ))}
            </View>
          )}

          {/* Start Inspection Button */}
          <Button
            mode="contained"
            icon="clipboard-plus"
            onPress={handleStartInspection}
            style={styles.startButton}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('verify.startInspection')}
          </Button>
        </ScrollView>
      )}
      {/* QR Scanner Modal */}
      <Modal
        visible={showScanner}
        animationType="slide"
        onRequestClose={() => setShowScanner(false)}
      >
        <QRScanner
          onScan={handleQRScan}
          onClose={() => setShowScanner(false)}
        />
      </Modal>

      {/* Snackbar for invalid QR */}
      <Snackbar
        visible={!!snackMessage}
        onDismiss={() => setSnackMessage('')}
        duration={3000}
        action={{ label: 'OK', onPress: () => setSnackMessage('') }}
      >
        {snackMessage}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingBottom: 8 },
  qrSection: { alignItems: 'center', paddingHorizontal: 16, paddingBottom: 12 },
  qrButton: { borderRadius: 8, width: '100%' },
  searchBar: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8 },
  searchInput: { flex: 1, backgroundColor: 'transparent' },
  searchButton: { alignSelf: 'center', borderRadius: 8 },
  error: { paddingHorizontal: 16 },
  results: { paddingBottom: 32 },
  companyHeader: { margin: 16, padding: 16, borderRadius: 8 },
  companyMeta: { gap: 2, marginTop: 4 },
  companyStats: { flexDirection: 'row', justifyContent: 'space-between' },
  statCol: { alignItems: 'center', gap: 2 },
  section: { marginHorizontal: 16, marginBottom: 16 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  obligationItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 4,
  },
  obligationRestricted: {
    opacity: 0.55,
  },
  obligationsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  infoBanner: {
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  warningBanner: {
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  prevItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    height: 44,
    paddingHorizontal: 4,
  },
  medWarning: {
    marginHorizontal: 16,
    marginBottom: 16,
    padding: 12,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  scopeBadge: {
    marginHorizontal: 16,
    marginBottom: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  startButton: { marginHorizontal: 16, marginTop: 8, borderRadius: 8 },
});
