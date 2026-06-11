/**
 * Vault upload screen — pick a file from camera, gallery or document picker,
 * compute SHA-256, run check-hash, and POST /upload.
 *
 * Strict client-side gates BEFORE bytes leave the device:
 *   - MIME whitelist (pdf/jpeg/png/webp) matching backend OWASP magic-bytes.
 *   - Size cap (10 MB).
 *   - SHA-256 dedup pre-check; if a duplicate exists, surface a modal so the
 *     user can either reuse the existing vault doc or force a fresh upload.
 */

import React, { useCallback, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Appbar,
  Button,
  Card,
  Dialog,
  HelperText,
  Portal,
  ProgressBar,
  Snackbar,
  Text,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useUploadVaultDocument } from '@modules/vault';
import {
  VAULT_ALLOWED_MIME_TYPES,
  VAULT_MAX_FILE_SIZE_BYTES,
  type VaultAllowedMime,
} from '@modules/vault';

interface PickedFile {
  uri: string;
  name: string;
  mimeType: VaultAllowedMime;
  size: number;
}

function inferMime(name: string, mimeHint?: string | null): VaultAllowedMime | null {
  const lower = name.toLowerCase();
  if (mimeHint && (VAULT_ALLOWED_MIME_TYPES as readonly string[]).includes(mimeHint)) {
    return mimeHint as VaultAllowedMime;
  }
  if (lower.endsWith('.pdf')) return 'application/pdf';
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  return null;
}

export default function UploadScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [picked, setPicked] = useState<PickedFile | null>(null);
  const [hint, setHint] = useState('');
  const [notes, setNotes] = useState('');
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [duplicateDialog, setDuplicateDialog] = useState(false);

  const upload = useUploadVaultDocument();

  const pickFromCamera = useCallback(async () => {
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      quality: 0.85,
      allowsEditing: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    const mime = inferMime(asset.fileName ?? 'photo.jpg', asset.mimeType);
    if (!mime) {
      setSnackbar(t('vault.errors.mime_invalid'));
      return;
    }
    setPicked({
      uri: asset.uri,
      name: asset.fileName ?? 'photo.jpg',
      mimeType: mime,
      size: asset.fileSize ?? 0,
    });
  }, [t]);

  const pickFromGallery = useCallback(async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.85,
      allowsEditing: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    const mime = inferMime(asset.fileName ?? 'image.jpg', asset.mimeType);
    if (!mime) {
      setSnackbar(t('vault.errors.mime_invalid'));
      return;
    }
    setPicked({
      uri: asset.uri,
      name: asset.fileName ?? 'image.jpg',
      mimeType: mime,
      size: asset.fileSize ?? 0,
    });
  }, [t]);

  const pickDocument = useCallback(async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: [...VAULT_ALLOWED_MIME_TYPES],
      copyToCacheDirectory: true,
      multiple: false,
    });
    if (result.canceled || !result.assets[0]) return;
    const asset = result.assets[0];
    const mime = inferMime(asset.name, asset.mimeType);
    if (!mime) {
      setSnackbar(t('vault.errors.mime_invalid'));
      return;
    }
    if (asset.size && asset.size > VAULT_MAX_FILE_SIZE_BYTES) {
      setSnackbar(t('vault.errors.file_too_large'));
      return;
    }
    setPicked({
      uri: asset.uri,
      name: asset.name,
      mimeType: mime,
      size: asset.size ?? 0,
    });
  }, [t]);

  const performUpload = useCallback(
    (skipDedup: boolean) => {
      if (!picked) return;
      upload.mutate(
        {
          fileUri: picked.uri,
          fileName: picked.name,
          mimeType: picked.mimeType,
          documentTypeHint: hint.trim() || undefined,
          notes: notes.trim() || undefined,
          skipDedup,
        },
        {
          onSuccess: (outcome) => {
            if (outcome.duplicate) {
              setDuplicateDialog(true);
              return;
            }
            setSnackbar(t('vault.upload.success'));
            // Best-effort navigate to the new doc
            const newId = outcome.result?.id;
            if (newId) {
              router.replace(`/documents/${newId}` as never);
            } else {
              router.back();
            }
          },
          onError: (err) => {
            const message = err instanceof Error ? err.message : t('vault.errors.unknown');
            setSnackbar(message);
          },
        },
      );
    },
    [hint, notes, picked, t, upload],
  );

  const handleUpload = useCallback(() => performUpload(false), [performUpload]);
  const handleForceUpload = useCallback(() => {
    setDuplicateDialog(false);
    performUpload(true);
  }, [performUpload]);

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={t('vault.upload.title')} />
      </Appbar.Header>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.pickerRow}>
          <Button
            mode="outlined"
            icon="camera"
            onPress={pickFromCamera}
            disabled={upload.isPending}
            style={styles.pickerButton}
          >
            {t('vault.upload.picker.camera')}
          </Button>
          <Button
            mode="outlined"
            icon="image-multiple"
            onPress={pickFromGallery}
            disabled={upload.isPending}
            style={styles.pickerButton}
          >
            {t('vault.upload.picker.gallery')}
          </Button>
          <Button
            mode="outlined"
            icon="file-document-outline"
            onPress={pickDocument}
            disabled={upload.isPending}
            style={styles.pickerButton}
          >
            {t('vault.upload.picker.document')}
          </Button>
        </View>

        {picked ? (
          <Card style={styles.previewCard}>
            <Card.Content>
              <View style={styles.previewRow}>
                <MaterialCommunityIcons
                  name={picked.mimeType === 'application/pdf' ? 'file-pdf-box' : 'file-image'}
                  size={36}
                  color={colors.primary}
                />
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text variant="titleSmall" numberOfLines={1}>
                    {picked.name}
                  </Text>
                  <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                    {picked.mimeType} · {(picked.size / 1024).toFixed(1)} KB
                  </Text>
                </View>
              </View>
            </Card.Content>
          </Card>
        ) : null}

        {picked ? (
          <View style={styles.fields}>
            <TextInput
              label={t('vault.upload.fields.documentTypeHint')}
              value={hint}
              onChangeText={setHint}
              mode="outlined"
              autoCapitalize="none"
              style={styles.input}
            />
            <HelperText type="info">{t('vault.upload.fields.documentTypeHintHelp')}</HelperText>
            <TextInput
              label={t('vault.upload.fields.notes')}
              value={notes}
              onChangeText={setNotes}
              mode="outlined"
              multiline
              numberOfLines={3}
              style={styles.input}
            />
          </View>
        ) : null}

        {upload.isPending ? (
          <View style={styles.progressWrap}>
            <ActivityIndicator color={colors.primary} />
            <ProgressBar indeterminate color={colors.primary} style={styles.progressBar} />
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {t('vault.upload.uploading')}
            </Text>
          </View>
        ) : null}

        {picked && !upload.isPending ? (
          <Button mode="contained" onPress={handleUpload} style={styles.uploadButton}>
            {t('vault.upload.actions.upload')}
          </Button>
        ) : null}
      </ScrollView>

      <Portal>
        <Dialog visible={duplicateDialog} onDismiss={() => setDuplicateDialog(false)}>
          <Dialog.Title>{t('vault.upload.duplicate.title')}</Dialog.Title>
          <Dialog.Content>
            <Text>{t('vault.upload.duplicate.body')}</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDuplicateDialog(false)}>
              {t('common.cancel')}
            </Button>
            <Button onPress={handleForceUpload}>
              {t('vault.upload.duplicate.replace')}
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { padding: 16, gap: 16 },
  pickerRow: {
    flexDirection: 'row',
    gap: 8,
    justifyContent: 'space-between',
  },
  pickerButton: { flex: 1 },
  previewCard: {},
  previewRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  fields: { gap: 4 },
  input: { backgroundColor: 'transparent' },
  progressWrap: { alignItems: 'center', gap: 12 },
  progressBar: { width: '100%', height: 4, borderRadius: 2 },
  uploadButton: { marginTop: 12 },
});
