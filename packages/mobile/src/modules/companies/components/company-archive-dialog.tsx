/**
 * Company Archive Dialog (citizen surface, mobile).
 *
 * Two states:
 *   1. Idle / submitting — explains the soft-delete contract.
 *   2. Blocked (after a 409) — lists the per-bucket blockers and offers a
 *      "Voir mes obligations" deep-link.
 *
 * Mirrors the web ArchiveCompanyDialog (commit 184c4069) so both surfaces
 * read identically. Backend reference:
 * POST /api/v1/companies/{id}/archive (Phase 1 of SOFT_DELETE_COMPANIES_PLAN).
 */

import React, { useEffect, useMemo } from 'react';
import { View } from 'react-native';
import {
  Button,
  Dialog,
  Portal,
  Text,
  ActivityIndicator,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import {
  getArchiveBlockers,
  isArchiveBlockedError,
  useArchiveCompany,
  type ArchiveBlockers,
} from '@modules/companies';

interface Props {
  visible: boolean;
  companyId: string;
  companyName: string;
  onCancel: () => void;
  onSuccess?: () => void;
  /** Optional callback to navigate to the obligations tab when blocked. */
  onSeeObligations?: () => void;
}

const BLOCKER_KEYS: (keyof ArchiveBlockers)[] = [
  'active_licenses',
  'pending_payments',
  'open_requests',
  'active_inspections',
];

export function CompanyArchiveDialog({
  visible,
  companyId,
  companyName,
  onCancel,
  onSuccess,
  onSeeObligations,
}: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const archive = useArchiveCompany();

  const blockers = useMemo<ArchiveBlockers | null>(
    () => getArchiveBlockers(archive.error),
    [archive.error],
  );
  const blocked = !!blockers && BLOCKER_KEYS.some((k) => (blockers[k] ?? 0) > 0);

  // Reset mutation state when the dialog closes so re-opening starts clean.
  useEffect(() => {
    if (!visible) archive.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  const handleConfirm = () => {
    archive.mutate(companyId, {
      onSuccess: () => {
        archive.reset();
        onCancel();
        onSuccess?.();
      },
    });
  };

  const isUnknownError =
    archive.isError && !isArchiveBlockedError(archive.error);

  return (
    <Portal>
      <Dialog visible={visible} onDismiss={onCancel}>
        <Dialog.Title>
          {blocked
            ? t('companies.archive.blockedTitle')
            : t('companies.archive.title')}
        </Dialog.Title>
        <Dialog.Content>
          {blocked ? (
            <View>
              <Text variant="bodyMedium" style={{ marginBottom: 12 }}>
                {t('companies.archive.blockedBody', { name: companyName })}
              </Text>
              {BLOCKER_KEYS.filter((k) => (blockers?.[k] ?? 0) > 0).map((k) => (
                <View
                  key={k}
                  style={{
                    flexDirection: 'row',
                    alignItems: 'center',
                    marginBottom: 6,
                  }}
                >
                  <MaterialCommunityIcons
                    name="alert-circle-outline"
                    size={16}
                    color={colors.error}
                  />
                  <Text variant="bodySmall" style={{ marginLeft: 6 }}>
                    {t(`companies.archive.blockers.${k}`, {
                      count: blockers?.[k] ?? 0,
                    })}
                  </Text>
                </View>
              ))}
              <Text
                variant="bodySmall"
                style={{ marginTop: 12, color: colors.onSurfaceVariant }}
              >
                {t('companies.archive.blockedHint')}
              </Text>
            </View>
          ) : (
            <View>
              <Text variant="bodyMedium" style={{ marginBottom: 12 }}>
                {t('companies.archive.body', { name: companyName })}
              </Text>
              <Text
                variant="bodySmall"
                style={{ color: colors.onSurfaceVariant }}
              >
                {t('companies.archive.disclaimer')}
              </Text>
            </View>
          )}

          {isUnknownError ? (
            <Text
              variant="bodySmall"
              style={{ color: colors.error, marginTop: 12 }}
            >
              {archive.error instanceof Error
                ? archive.error.message
                : t('common.error')}
            </Text>
          ) : null}

          {archive.isPending ? (
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                marginTop: 12,
              }}
            >
              <ActivityIndicator size="small" color={colors.primary} />
              <Text variant="bodySmall" style={{ marginLeft: 8 }}>
                {t('companies.archive.submitting')}
              </Text>
            </View>
          ) : null}
        </Dialog.Content>
        <Dialog.Actions>
          <Button onPress={onCancel} disabled={archive.isPending}>
            {blocked ? t('common.close') : t('common.cancel')}
          </Button>
          {blocked && onSeeObligations ? (
            <Button mode="contained" onPress={onSeeObligations}>
              {t('companies.archive.seeObligations')}
            </Button>
          ) : !blocked ? (
            <Button
              mode="contained"
              onPress={handleConfirm}
              disabled={archive.isPending}
              loading={archive.isPending}
            >
              {t('companies.archive.confirm')}
            </Button>
          ) : null}
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}
