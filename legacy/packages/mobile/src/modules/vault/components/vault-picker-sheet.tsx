/**
 * VaultPickerSheet — bottom sheet to pick an existing vault document for
 * a wizard step (auto-fill instead of re-upload).
 *
 * Filtering rules (mobile-side, since the backend doesn't validate
 * document_code ↔ vault.document_type):
 *   1. Fetch `useDocumentsForWorkflow(workflowCode)` — backend already
 *      returns vault docs matching the workflow's required types.
 *   2. Further filter by `document_type === (documentTypeHint ?? documentCode)`
 *      so the picker only shows docs the user can confidently use here.
 */

import React, { useMemo } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Button,
  Dialog,
  Divider,
  Portal,
  Text,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';

import { useAppTheme } from '@core/theme';
import { useDocumentsForWorkflow } from '../services/vault-hooks';
import { DocumentListItem } from './document-list-item';
import type { UserDocumentListItem, UserDocumentResponse } from '../types/vault.types';

interface VaultPickerSheetProps {
  visible: boolean;
  workflowCode: string;
  documentCode: string;
  /** Optional vault `document_type` to pre-filter. Defaults to documentCode. */
  documentTypeHint?: string;
  loading?: boolean;
  onCancel: () => void;
  onSelect: (vaultDocumentId: string) => void;
}

export function VaultPickerSheet({
  visible,
  workflowCode,
  documentCode,
  documentTypeHint,
  loading,
  onCancel,
  onSelect,
}: VaultPickerSheetProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const docs = useDocumentsForWorkflow(visible ? workflowCode : null);

  const filtered = useMemo(() => {
    const target = (documentTypeHint ?? documentCode).toLowerCase();
    return (docs.data ?? []).filter(
      (d) => (d.document_type ?? '').toLowerCase() === target,
    );
  }, [docs.data, documentCode, documentTypeHint]);

  const handleEmptyCta = () => {
    onCancel();
    router.push('/documents/upload' as never);
  };

  const handleSelect = (item: UserDocumentResponse) => {
    onSelect(item.id);
  };

  return (
    <Portal>
      <Dialog visible={visible} onDismiss={onCancel} style={styles.dialog}>
        <Dialog.Title>{t('vault.picker.title')}</Dialog.Title>
        <Dialog.Content>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginBottom: 12 }}>
            {t('vault.picker.subtitle', { documentCode })}
          </Text>
          {docs.isLoading ? (
            <View style={styles.center}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : filtered.length === 0 ? (
            <View style={styles.center}>
              <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, textAlign: 'center' }}>
                {t('vault.picker.empty')}
              </Text>
            </View>
          ) : (
            <FlatList
              data={filtered}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <DocumentListItem
                  // The picker also shows full UserDocumentResponse — the
                  // list-item component reads only the subset of fields
                  // present in both shapes.
                  item={item as unknown as UserDocumentListItem}
                  onPress={() => handleSelect(item)}
                />
              )}
              ItemSeparatorComponent={() => <Divider />}
              style={styles.list}
            />
          )}
        </Dialog.Content>
        <Dialog.Actions>
          <Button onPress={onCancel} disabled={loading}>
            {t('common.cancel')}
          </Button>
          {filtered.length === 0 && !docs.isLoading ? (
            <Button onPress={handleEmptyCta}>{t('vault.picker.goToVault')}</Button>
          ) : null}
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}

const styles = StyleSheet.create({
  dialog: {
    maxHeight: '80%',
  },
  list: {
    maxHeight: 360,
  },
  center: {
    paddingVertical: 24,
    alignItems: 'center',
  },
});
