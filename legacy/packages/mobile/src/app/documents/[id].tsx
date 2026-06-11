/**
 * Vault document detail screen.
 *
 * - Header with back + overflow menu (archive / delete / reclassify).
 * - Preview: thumbnail when available, else mime icon + "Open" button that
 *   uses the Firebase signed URL (15-min TTL — refreshed via React Query
 *   staleTime).
 * - Metadata panel + extraction data (collapsible).
 * - Polls extraction_status every 2s while not in {completed, failed}.
 */

import React, { useCallback, useState } from 'react';
import { Linking, ScrollView, StyleSheet, View } from 'react-native';
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
import { Image } from 'expo-image';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import {
  useArchiveVaultDocument,
  useDeleteVaultDocument,
  useDownloadUrl,
  useThumbnailUrl,
  useVaultDocument,
} from '@modules/vault';

function formatBytes(bytes: number): string {
  if (!bytes) return '0 KB';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function formatDate(iso: string | null | undefined, locale: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString(locale);
  } catch {
    return iso;
  }
}

export default function DocumentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t, i18n } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const [menuVisible, setMenuVisible] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const doc = useVaultDocument(id ?? null);
  const thumbnail = useThumbnailUrl(id ?? null);
  const archive = useArchiveVaultDocument();
  const remove = useDeleteVaultDocument();

  const fetchDownload = useDownloadUrl(id ?? null);

  const handleOpen = useCallback(async () => {
    const url = fetchDownload.data?.url;
    if (!url) return;
    const can = await Linking.canOpenURL(url);
    if (can) {
      await Linking.openURL(url);
    } else {
      setSnackbar(t('vault.detail.openFailed'));
    }
  }, [fetchDownload.data?.url, t]);

  const handleArchive = useCallback(() => {
    if (!id) return;
    setMenuVisible(false);
    archive.mutate(id, {
      onSuccess: () => setSnackbar(t('vault.detail.archived')),
      onError: () => setSnackbar(t('vault.errors.unknown')),
    });
  }, [archive, id, t]);

  const handleDelete = useCallback(() => {
    if (!id) return;
    setMenuVisible(false);
    remove.mutate(id, {
      onSuccess: () => {
        setSnackbar(t('vault.detail.deleted'));
        router.back();
      },
      onError: () => setSnackbar(t('vault.errors.unknown')),
    });
  }, [remove, id, t]);

  const lang = (i18n.language ?? 'es').slice(0, 2);
  const isImage = doc.data?.mime_type?.startsWith('image/');
  const isPending =
    doc.data?.extraction_status &&
    doc.data.extraction_status !== 'completed' &&
    doc.data.extraction_status !== 'failed';

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content
          title={doc.data?.display_name ?? doc.data?.file_name ?? t('vault.detail.loading')}
        />
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
          <Menu.Item
            onPress={handleArchive}
            leadingIcon="archive-outline"
            title={t('vault.detail.actions.archive')}
            disabled={archive.isPending}
          />
          <Menu.Item
            onPress={handleDelete}
            leadingIcon="trash-can-outline"
            title={t('vault.detail.actions.delete')}
            disabled={remove.isPending}
          />
        </Menu>
      </Appbar.Header>

      {doc.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : !doc.data ? (
        <View style={styles.center}>
          <Text variant="titleSmall" style={{ color: colors.error }}>
            {t('vault.detail.loadError')}
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 32 + insets.bottom }}>
          {/* Preview */}
          <View style={styles.previewWrap}>
            {isImage && thumbnail.data?.url ? (
              <Image
                source={{ uri: thumbnail.data.url }}
                style={styles.previewImage}
                contentFit="cover"
              />
            ) : (
              <View style={[styles.previewPlaceholder, { backgroundColor: colors.surfaceVariant }]}>
                <MaterialCommunityIcons
                  name={doc.data.mime_type === 'application/pdf' ? 'file-pdf-box' : 'file-document-outline'}
                  size={64}
                  color={colors.primary}
                />
              </View>
            )}
            <Button
              mode="contained"
              icon="open-in-new"
              onPress={handleOpen}
              loading={fetchDownload.isFetching}
              disabled={fetchDownload.isFetching || !fetchDownload.data?.url}
              style={styles.openButton}
            >
              {t('vault.detail.actions.open')}
            </Button>
          </View>

          {/* Pending banner */}
          {isPending ? (
            <Card style={[styles.card, { backgroundColor: colors.primaryContainer }]}>
              <Card.Content style={styles.pendingRow}>
                <ActivityIndicator size="small" color={colors.onPrimaryContainer} />
                <Text style={{ color: colors.onPrimaryContainer, marginLeft: 12 }}>
                  {t('vault.detail.processing')}
                </Text>
              </Card.Content>
            </Card>
          ) : null}

          {/* Metadata */}
          <Card style={styles.card}>
            <Card.Title title={t('vault.detail.sections.metadata')} />
            <Card.Content>
              <Field label={t('vault.detail.fields.documentType')} value={doc.data.document_type ?? '—'} />
              <Field label={t('vault.detail.fields.holderName')} value={doc.data.holder_name ?? '—'} />
              <Field label={t('vault.detail.fields.documentNumber')} value={doc.data.document_number ?? '—'} />
              <Field
                label={t('vault.detail.fields.expiryDate')}
                value={formatDate(doc.data.expiry_date, lang)}
              />
              <Field
                label={t('vault.detail.fields.fileSize')}
                value={formatBytes(doc.data.file_size_bytes ?? 0)}
              />
              <Field
                label={t('vault.detail.fields.createdAt')}
                value={formatDate(doc.data.created_at, lang)}
              />
            </Card.Content>
          </Card>

          {/* Extraction */}
          {doc.data.extracted_data && Object.keys(doc.data.extracted_data).length > 0 ? (
            <Card style={styles.card}>
              <Card.Title title={t('vault.detail.sections.extraction')} />
              <Card.Content>
                {Object.entries(doc.data.extracted_data as Record<string, unknown>).map(([k, v]) => (
                  <Field key={k} label={k} value={String(v ?? '—')} />
                ))}
              </Card.Content>
            </Card>
          ) : null}
        </ScrollView>
      )}

      <Snackbar
        visible={!!snackbar}
        onDismiss={() => setSnackbar(null)}
        duration={3000}
      >
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
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
  previewWrap: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 12,
  },
  previewImage: {
    width: '100%',
    height: 220,
    borderRadius: 8,
  },
  previewPlaceholder: {
    width: '100%',
    height: 220,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  openButton: {
    alignSelf: 'flex-start',
  },
  card: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  pendingRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  field: {
    marginBottom: 8,
  },
  fieldDivider: {
    marginTop: 6,
  },
});
