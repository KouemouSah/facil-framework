/**
 * Company detail (citizen view) — wired on
 *   GET /bundle-workflow/my-companies/{id}
 *   GET /bundle-workflow/my-companies/{id}/payments
 *
 * Mirrors the web /empresas/[id] page: license status, obligations list with
 * "Pagar Obligaciones" CTA, payment history, company info, members preview.
 */

import React, { useCallback, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Appbar,
  Button,
  Card,
  Divider,
  Menu,
  Snackbar,
  Text,
} from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { CompanyArchiveDialog } from '@modules/companies/components/company-archive-dialog';
import {
  useCompanyMembers,
  useCompanyMembership,
  useDownloadLicensePdf,
} from '@modules/companies';
import {
  useBundleMyCompanyDetail,
  type LicenseObligation,
} from '@modules/bundles';

function statusColor(status: string | null, colors: ReturnType<typeof useAppTheme>['colors']) {
  switch (status) {
    case 'active':
    case 'paid':
      return colors.tertiary;
    case 'pending':
    case 'pending_payment':
    case 'draft':
      return colors.primary;
    case 'overdue':
    case 'expired':
    case 'revoked':
    case 'cancelled':
      return colors.error;
    default:
      return colors.outline;
  }
}

export default function CompanyDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { user } = useAuth();
  const insets = useSafeAreaInsets();
  const [menuVisible, setMenuVisible] = useState(false);
  const [archiveVisible, setArchiveVisible] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const detail = useBundleMyCompanyDetail(id);
  const members = useCompanyMembers(id ?? null);
  const downloadPdf = useDownloadLicensePdf();

  const company = detail.data?.company ?? null;
  const license = detail.data?.license ?? null;
  const obligations = detail.data?.obligations ?? [];

  const pendingObligations = useMemo(
    () => obligations.filter((o) => o.status === 'pending' || o.status === 'overdue'),
    [obligations],
  );

  // Soft-delete (archive) — citizen surface, owner-only. Mirrors web
  // /empresas/[companyId] (commit 184c4069). Edit / hard-delete remain off
  // the citizen surface (backend gates them via company.hard_delete +
  // archived prerequisite — admin only).
  const { canArchive, canManageMembers } = useCompanyMembership(id ?? null, user?.id);

  const handleDownloadPdf = useCallback(() => {
    if (!id) return;
    setMenuVisible(false);
    downloadPdf.mutate(
      { companyId: id, language: 'es' },
      {
        onError: (err) =>
          setSnackbar(err instanceof Error ? err.message : t('companies.errors.unknown')),
      },
    );
  }, [downloadPdf, id, t]);

  const handlePayObligations = useCallback(() => {
    if (!id) return;
    router.push(`/bundle-wizard?company_id=${encodeURIComponent(id)}` as never);
  }, [id]);

  // members data is still consumed by useCompanyMembership above for the
  // role gate — even though we no longer render a member-preview card.
  // Reading it here keeps the query warm so canManageMembers stays accurate.
  void members.data;

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={company?.legal_name ?? t('companies.detail.loading')} />
        <Menu
          visible={menuVisible}
          onDismiss={() => setMenuVisible(false)}
          anchor={
            <Appbar.Action
              icon="dots-vertical"
              onPress={() => setMenuVisible(true)}
              accessibilityLabel={t('common.actions')}
            />
          }
        >
          {/* Download license PDF moved out of the kebab to a primary CTA
              inside the Licence Card — see debug/tesoro/m2.jpg user feedback
              ("button hidden in the three-dots menu"). Conversely, the
              payment history (previously rendered inline on this screen) is
              demoted into the kebab so the detail surface reads clean
              (license summary + obligations + info), m14.jpg fix
              2026-04-29. */}
          <Menu.Item
            onPress={() => {
              setMenuVisible(false);
              router.push(`/companies/${id}/payments` as never);
            }}
            leadingIcon="receipt-text-outline"
            title={t('companies.detail.actions.viewPayments')}
          />
          {canManageMembers ? (
            <Menu.Item
              onPress={() => {
                setMenuVisible(false);
                router.push(`/companies/${id}/members` as never);
              }}
              leadingIcon="account-multiple-outline"
              title={t('companies.detail.actions.manageMembers')}
            />
          ) : null}
          {canArchive ? (
            <Menu.Item
              onPress={() => {
                setMenuVisible(false);
                setArchiveVisible(true);
              }}
              leadingIcon="archive-outline"
              title={t('companies.archive.menuLabel')}
            />
          ) : null}
        </Menu>
      </Appbar.Header>

      {detail.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : !company ? (
        <View style={styles.center}>
          <Text variant="titleSmall" style={{ color: colors.error }}>
            {t('companies.detail.loadError')}
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 32 + insets.bottom }}>
          {/* License status card — m14.jpg redesign 2026-04-29:
              status row + 3 colored summary chips (deadline / total / paid)
              for visual differentiation, then registration number, then a
              centered Download licence CTA. Replaces the 4 monochrome
              <Field> rows that read like a legal form. */}
          <Card style={styles.card}>
            <Card.Title title={t('companies.detail.sections.license')} />
            <Card.Content>
              {license ? (
                <>
                  <View style={styles.statusRow}>
                    <View
                      style={[styles.dot, { backgroundColor: statusColor(license.status, colors) }]}
                    />
                    <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
                      {t(`companies.license.status.${license.status}`, {
                        defaultValue: license.status,
                      })}
                    </Text>
                  </View>

                  <LicenseSummaryChips
                    deadline={license.deadline}
                    totalAmount={license.total_amount}
                    amountPaid={license.amount_paid}
                  />

                  <Field
                    label={t('companies.card.registrationNumber')}
                    value={company.registration_number ?? '—'}
                  />

                  {/* Primary CTA — promoted out of the kebab and now
                      horizontally centered as requested in m14.jpg. */}
                  <Button
                    mode="contained-tonal"
                    icon="file-download-outline"
                    onPress={handleDownloadPdf}
                    loading={downloadPdf.isPending}
                    disabled={downloadPdf.isPending}
                    style={{ marginTop: 16, alignSelf: 'center' }}
                    accessibilityLabel={t('companies.detail.actions.downloadLicense')}
                  >
                    {t('companies.detail.actions.downloadLicense')}
                  </Button>
                </>
              ) : (
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                  {t('companies.card.noLicense')}
                </Text>
              )}
            </Card.Content>
          </Card>

          {/* Obligations */}
          <Card style={styles.card}>
            <Card.Title title={t('companies.obligations.title')} />
            <Card.Content style={{ paddingHorizontal: 0 }}>
              {obligations.length === 0 ? (
                <Text
                  variant="bodySmall"
                  style={{ color: colors.onSurfaceVariant, paddingHorizontal: 16 }}
                >
                  {t('companies.obligations.empty')}
                </Text>
              ) : (
                obligations.map((o, i) => (
                  <View key={o.id}>
                    <ObligationRow obligation={o} />
                    {i < obligations.length - 1 ? <Divider /> : null}
                  </View>
                ))
              )}
              {pendingObligations.length > 0 ? (
                <Button
                  icon="cash-multiple"
                  mode="contained"
                  onPress={handlePayObligations}
                  style={{ marginTop: 12, marginHorizontal: 16 }}
                >
                  {t('companies.obligations.payAll')}
                </Button>
              ) : null}
            </Card.Content>
          </Card>

          {/* Payment history Card removed from the inline detail surface.
              Promoted to its own route /companies/[id]/payments via the
              kebab menu (m14.jpg fix 2026-04-29) so the detail screen reads
              clean and the history has its own scroll position. */}

          {/* Company info */}
          <Card style={styles.card}>
            <Card.Title title={t('companies.detail.sections.info')} />
            <Card.Content>
              <Field label={t('companies.form.fields.taxId')} value={company.nif ?? '—'} />
              <Field
                label={t('companies.form.fields.representanteLegal')}
                value={company.representante_legal ?? '—'}
              />
              <Field
                label={t('companies.form.fields.formaJuridica')}
                value={company.forma_juridica ?? '—'}
              />
              <Field
                label={t('companies.form.fields.regimenFiscal')}
                value={company.regimen_fiscal ?? '—'}
              />
              <Field
                label={t('companies.form.fields.cityName')}
                value={company.city_name ?? '—'}
              />
            </Card.Content>
          </Card>

          {/* Members preview removed — the web /empresas/[id] page does NOT
              expose member management on the citizen surface, only an
              admin-only /admin/companies/[id]/members route. We kept the
              `useCompanyMembers` hook above (it powers `useCompanyMembership`
              for the archive role gate); we just no longer render the section.
              See debug/tesoro/m2.jpg notes from the user. */}
        </ScrollView>
      )}

      {id ? (
        <CompanyArchiveDialog
          visible={archiveVisible}
          companyId={id}
          companyName={company?.legal_name ?? ''}
          onCancel={() => setArchiveVisible(false)}
          onSuccess={() => {
            setSnackbar(t('companies.archive.success'));
            // Wait briefly so the snackbar shows before navigating back.
            setTimeout(() => router.back(), 600);
          }}
          onSeeObligations={() => {
            setArchiveVisible(false);
            // The detail screen already shows the obligations list — closing
            // the dialog is sufficient. (Web equivalent uses a tab anchor.)
          }}
        />
      ) : null}

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

function ObligationRow({ obligation }: { obligation: LicenseObligation }) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  return (
    <View style={styles.row}>
      <View style={[styles.rowDot, { backgroundColor: statusColor(obligation.status, colors) }]} />
      <View style={styles.rowBody}>
        <Text
          variant="bodyMedium"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: '500' }}
        >
          {obligation.service_name ?? obligation.fee_type}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }} numberOfLines={1}>
          {obligation.ministry_name ?? ''}
          {obligation.due_date
            ? ` · ${t('companies.obligations.dueDate')}: ${new Date(
                obligation.due_date,
              ).toLocaleDateString()}`
            : ''}
        </Text>
      </View>
      <View style={styles.rowRight}>
        <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
          {obligation.amount.toLocaleString()} XAF
        </Text>
        <Text variant="labelSmall" style={{ color: statusColor(obligation.status, colors) }}>
          {t(`companies.obligations.status.${obligation.status}`, {
            defaultValue: obligation.status,
          })}
        </Text>
      </View>
    </View>
  );
}

/**
 * 3 colored summary chips replacing the monochrome <Field> rows for
 * deadline / total / paid (m14.jpg fix). Colors:
 *   • deadline → primary    (informational, neutral)
 *   • total    → tertiary   (positive — what the user owes total)
 *   • paid     → secondary  (progress — what the user has already paid)
 * The "paid" chip displays "amount_paid / total_amount" so the user sees
 * progress at a glance.
 */
function LicenseSummaryChips({
  deadline,
  totalAmount,
  amountPaid,
}: {
  deadline: string | null;
  totalAmount: number;
  amountPaid: number;
}) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const fmtAmount = (n: number) => n.toLocaleString();
  const fmtDate = (iso: string | null) =>
    iso ? new Date(iso).toLocaleDateString() : '—';

  return (
    <View style={styles.chipsRow}>
      <SummaryChip
        label={t('companies.detail.summary.deadline')}
        value={fmtDate(deadline)}
        background={colors.primaryContainer}
        foreground={colors.onPrimaryContainer}
      />
      <SummaryChip
        label={t('companies.detail.summary.total')}
        value={`${fmtAmount(totalAmount)} XAF`}
        background={colors.tertiaryContainer}
        foreground={colors.onTertiaryContainer}
      />
      <SummaryChip
        label={t('companies.detail.summary.paid')}
        value={`${fmtAmount(amountPaid)} / ${fmtAmount(totalAmount)}`}
        background={colors.secondaryContainer}
        foreground={colors.onSecondaryContainer}
      />
    </View>
  );
}

function SummaryChip({
  label,
  value,
  background,
  foreground,
}: {
  label: string;
  value: string;
  background: string;
  foreground: string;
}) {
  return (
    <View style={[styles.chip, { backgroundColor: background }]}>
      <Text style={[styles.chipLabel, { color: foreground }]} numberOfLines={1}>
        {label}
      </Text>
      <Text style={[styles.chipValue, { color: foreground }]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.field}>
      <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
        {label}
      </Text>
      <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
        {value}
      </Text>
      <Divider style={styles.fieldDivider} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  card: { marginHorizontal: 16, marginBottom: 12 },
  field: { marginBottom: 8 },
  fieldDivider: { marginTop: 6 },
  statusRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 12,
  },
  rowDot: { width: 8, height: 8, borderRadius: 4 },
  rowBody: { flex: 1 },
  rowRight: { alignItems: 'flex-end' },

  // License summary chips — m14.jpg redesign 2026-04-29.
  chipsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  chip: {
    flex: 1,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipLabel: {
    fontSize: 11,
    fontWeight: '500',
    opacity: 0.85,
    marginBottom: 2,
  },
  chipValue: {
    fontSize: 13,
    fontWeight: '700',
  },
});
