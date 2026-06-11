import { useState, useCallback, useMemo } from 'react';
import {
  StyleSheet,
  View,
  FlatList,
  Alert,
  type ListRenderItemInfo,
} from 'react-native';
import {
  Text,
  IconButton,
  ActivityIndicator,
  Divider,
  TouchableRipple,
  Snackbar,
} from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { useAppTheme } from '@core/theme';
import type { WizardRequiredDocument, DocumentPreview } from '../types/wizard.types';
import { useVaultReadinessForWorkflow, VaultPickerSheet } from '@modules/vault';
import * as wizardApi from '../services/wizard-api';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepUploadProps {
  requiredDocuments: WizardRequiredDocument[];
  uploadingDocuments: Set<string>;
  onUploadDocument: (
    documentCode: string,
    fileUri: string,
    fileName: string,
  ) => Promise<DocumentPreview>;
  onDeleteDocument: (documentCode: string) => Promise<void>;
  onDocumentPreview: (preview: DocumentPreview) => void;
  /** Optional — when provided enables the "Depuis le coffre" auto-fill flow. */
  sessionId?: string;
  /** Optional — required alongside sessionId for the vault picker. */
  workflowCode?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COMPRESS_WIDTH = 1500;
const COMPRESS_QUALITY = 0.7;
// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepUpload({
  requiredDocuments,
  uploadingDocuments,
  onUploadDocument,
  onDeleteDocument,
  onDocumentPreview,
  sessionId,
  workflowCode,
}: StepUploadProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const queryClient = useQueryClient();
  const [deletingDocs, setDeletingDocs] = useState<Set<string>>(new Set());
  const [isCompressing, setIsCompressing] = useState(false);
  const [pickerFor, setPickerFor] = useState<WizardRequiredDocument | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  // Vault readiness drives whether the "Depuis le coffre" option appears.
  // Only fetched when both sessionId and workflowCode are provided AND the
  // user is authenticated (the hook itself is gated on workflowCode != null).
  const readiness = useVaultReadinessForWorkflow(
    sessionId && workflowCode ? workflowCode : null,
  );

  /** Map { document_code → vault_document_id } for ready vault docs. */
  const vaultByCode = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of readiness.data?.ready ?? []) {
      if (item.vault_document_id) map.set(item.code, item.vault_document_id);
    }
    return map;
  }, [readiness.data]);

  const useVaultMutation = useMutation({
    mutationFn: ({
      documentCode,
      vaultDocumentId,
    }: {
      documentCode: string;
      vaultDocumentId: string;
    }) =>
      wizardApi.useVaultDocument(sessionId as string, {
        document_code: documentCode,
        vault_document_id: vaultDocumentId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wizard-session', sessionId] });
      queryClient.invalidateQueries({ queryKey: ['vault', 'readiness', workflowCode] });
      setSnackbar(t('wizard.upload.vault.success'));
    },
    onError: () => {
      setSnackbar(t('wizard.upload.vault.error'));
    },
  });

  // ── Image compression ────────────────────────────────────────────────

  const compressImage = useCallback(async (uri: string): Promise<string> => {
    const result = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: COMPRESS_WIDTH } }],
      { compress: COMPRESS_QUALITY, format: ImageManipulator.SaveFormat.JPEG },
    );
    return result.uri;
  }, []);

  // ── Image picking ────────────────────────────────────────────────────

  const pickFromCamera = useCallback(async (): Promise<ImagePicker.ImagePickerAsset | null> => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        t('wizard.upload.permissionRequired'),
        t('wizard.upload.cameraPermissionMessage'),
      );
      return null;
    }
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.length) return null;
    return result.assets[0];
  }, [t]);

  const pickFromGallery = useCallback(async (): Promise<ImagePicker.ImagePickerAsset | null> => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert(
        t('wizard.upload.permissionRequired'),
        t('wizard.upload.galleryPermissionMessage'),
      );
      return null;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      quality: 0.8,
    });
    if (result.canceled || !result.assets?.length) return null;
    return result.assets[0];
  }, [t]);

  // ── Upload handler ───────────────────────────────────────────────────

  const handlePickDocument = useCallback(
    (doc: WizardRequiredDocument) => {
      const vaultDocId = vaultByCode.get(doc.code);
      const buttons: { text: string; onPress?: () => void; style?: 'cancel' | 'destructive' }[] = [
        {
          text: t('wizard.upload.camera'),
          onPress: async () => {
            const asset = await pickFromCamera();
            if (!asset) return;
            setIsCompressing(true);
            let compressedUri: string;
            try {
              compressedUri = await compressImage(asset.uri);
            } finally {
              setIsCompressing(false);
            }
            const fileName = asset.fileName ?? `${doc.code}_${Date.now()}.jpg`;
            try {
              const preview = await onUploadDocument(doc.code, compressedUri, fileName);
              onDocumentPreview(preview);
            } catch {
              Alert.alert(t('wizard.upload.error'), t('wizard.upload.uploadFailed'));
            }
          },
        },
        {
          text: t('wizard.upload.gallery'),
          onPress: async () => {
            const asset = await pickFromGallery();
            if (!asset) return;
            setIsCompressing(true);
            let compressedUri: string;
            try {
              compressedUri = await compressImage(asset.uri);
            } finally {
              setIsCompressing(false);
            }
            const fileName = asset.fileName ?? `${doc.code}_${Date.now()}.jpg`;
            try {
              const preview = await onUploadDocument(doc.code, compressedUri, fileName);
              onDocumentPreview(preview);
            } catch {
              Alert.alert(t('wizard.upload.error'), t('wizard.upload.uploadFailed'));
            }
          },
        },
      ];
      if (vaultDocId) {
        buttons.push({
          text: t('wizard.upload.vault.fromVault'),
          onPress: () => setPickerFor(doc),
        });
      }
      buttons.push({ text: t('common.cancel'), style: 'cancel' });
      Alert.alert(t('wizard.upload.selectSource'), undefined, buttons);
    },
    [
      pickFromCamera,
      pickFromGallery,
      compressImage,
      onUploadDocument,
      onDocumentPreview,
      t,
      vaultByCode,
    ],
  );

  const handleVaultSelect = useCallback(
    (vaultDocumentId: string) => {
      if (!pickerFor) return;
      const docCode = pickerFor.code;
      setPickerFor(null);
      useVaultMutation.mutate({ documentCode: docCode, vaultDocumentId });
    },
    [pickerFor, useVaultMutation],
  );

  // ── Delete handler ───────────────────────────────────────────────────

  const handleDelete = useCallback(
    async (docCode: string) => {
      Alert.alert(t('wizard.upload.deleteTitle'), t('wizard.upload.deleteMessage'), [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.delete'),
          style: 'destructive',
          onPress: async () => {
            setDeletingDocs((prev) => new Set(prev).add(docCode));
            try {
              await onDeleteDocument(docCode);
            } catch {
              Alert.alert(t('wizard.upload.error'), t('wizard.upload.deleteFailed'));
            } finally {
              setDeletingDocs((prev) => {
                const next = new Set(prev);
                next.delete(docCode);
                return next;
              });
            }
          },
        },
      ]);
    },
    [onDeleteDocument, t],
  );

  // ── Row component ────────────────────────────────────────────────────

  const renderRow = useCallback(
    (item: WizardRequiredDocument) => {
      const isUploading = uploadingDocuments.has(item.code);
      const isDeleting = deletingDocs.has(item.code);

      return (
        <TouchableRipple
          onPress={() => !isUploading && !isDeleting && handlePickDocument(item)}
          style={[
            styles.row,
            { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
          ]}
          disabled={isUploading || isDeleting}
        >
          <View style={styles.rowInner}>
            <MaterialCommunityIcons
              name={item.uploaded ? 'file-check-outline' : 'file-upload-outline'}
              size={22}
              color={item.uploaded ? colors.success : colors.outline}
              style={{ marginRight: spacing.sm }}
            />
            <View style={styles.textContainer}>
              <Text variant="bodyMedium" style={{ color: colors.onSurface }} numberOfLines={1}>
                {item.name_es}
              </Text>
              <Text
                variant="bodySmall"
                style={{ color: item.uploaded ? colors.success : colors.outline, marginTop: 2 }}
              >
                {item.uploaded ? t('wizard.upload.uploaded') : t('wizard.upload.pending')}
              </Text>
            </View>

            {item.is_required && !item.uploaded && (
              <View style={[styles.badge, { backgroundColor: colors.errorContainer, borderRadius: borderRadius.sm }]}>
                <Text variant="labelSmall" style={{ color: colors.error, fontWeight: '600' }}>
                  {t('wizard.upload.required')}
                </Text>
              </View>
            )}

            {isUploading || isDeleting ? (
              <ActivityIndicator size={18} color={colors.primary} style={{ marginLeft: spacing.sm }} />
            ) : item.uploaded ? (
              <MaterialCommunityIcons name="check-circle" size={20} color={colors.success} style={{ marginLeft: spacing.sm }} />
            ) : (
              <MaterialCommunityIcons name="chevron-right" size={20} color={colors.outline} style={{ marginLeft: spacing.sm }} />
            )}
          </View>
        </TouchableRipple>
      );
    },
    [uploadingDocuments, deletingDocs, colors, spacing, borderRadius, t, handlePickDocument],
  );

  // ── Render ───────────────────────────────────────────────────────────

  const uploadedCount = requiredDocuments.filter((d) => d.uploaded).length;
  const requiredCount = requiredDocuments.filter((d) => d.is_required).length;

  return (
    <View style={styles.container}>
      {/* Header summary */}
      <View style={[styles.header, { paddingHorizontal: spacing.md, paddingVertical: spacing.sm }]}>
        <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
          {t('wizard.upload.title')}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.outline }}>
          {t('wizard.upload.progress', {
            uploaded: uploadedCount,
            total: requiredDocuments.length,
            required: requiredCount,
          })}
        </Text>
      </View>

      <Divider />

      {/* Document list */}
      <FlatList
        data={requiredDocuments}
        keyExtractor={(item) => item.code}
        renderItem={({ item }: ListRenderItemInfo<WizardRequiredDocument>) => (
          <View style={styles.rowWrapper}>
            {item.uploaded && (
              <View style={[styles.deleteAction, { backgroundColor: colors.error }]}>
                <IconButton
                  icon="delete-outline"
                  iconColor={colors.onError}
                  size={20}
                  onPress={() => handleDelete(item.code)}
                />
              </View>
            )}
            {renderRow(item)}
          </View>
        )}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: 46 }} />}
        contentContainerStyle={{ paddingBottom: spacing.xxl }}
      />

      {/* Compression overlay */}
      {isCompressing && (
        <View style={styles.compressingOverlay}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text variant="bodyMedium" style={{ color: colors.onSurface, marginTop: 8 }}>{t('wizard.upload.compressing')}</Text>
        </View>
      )}

      {/* Vault picker for the active document */}
      {sessionId && workflowCode && pickerFor ? (
        <VaultPickerSheet
          visible={!!pickerFor}
          workflowCode={workflowCode}
          documentCode={pickerFor.code}
          loading={useVaultMutation.isPending}
          onCancel={() => setPickerFor(null)}
          onSelect={handleVaultSelect}
        />
      ) : null}

      <Snackbar
        visible={!!snackbar}
        onDismiss={() => setSnackbar(null)}
        duration={3000}
      >
        {snackbar ?? ''}
      </Snackbar>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { gap: 2 },
  rowWrapper: { position: 'relative', overflow: 'hidden' },
  deleteAction: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    width: 80,
    justifyContent: 'center',
    alignItems: 'center',
  },
  row: { borderBottomWidth: 0 },
  rowInner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  textContainer: { flex: 1, marginRight: 8 },
  badge: { paddingHorizontal: 6, paddingVertical: 2, marginRight: 4 },
  compressingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.9)',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 10,
  },
});
