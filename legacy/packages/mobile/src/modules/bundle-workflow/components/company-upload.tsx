/**
 * CompanyUploadStep — Upload certificado padrón empresarial
 * Aligned with web CompanyUploadStep.tsx
 */

import { useCallback } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { Text, Button, ActivityIndicator } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import { useAppTheme } from '@core/theme';
import type { useBundleWizard } from '../services/bundle-hooks';

type Wizard = ReturnType<typeof useBundleWizard>;

export function CompanyUploadStep({ wizard, lang }: { wizard: Wizard; lang: string }) {
  const { colors } = useAppTheme();

  const labels: Record<string, Record<string, string>> = {
    title: { es: 'Certificado de Actualización del Padrón Empresarial', fr: 'Certificat de mise à jour du registre des entreprises', en: 'Business Registry Update Certificate' },
    desc: { es: 'Suba el certificado para registrar automáticamente su empresa', fr: 'Téléchargez le certificat pour enregistrer automatiquement votre entreprise', en: 'Upload the certificate to automatically register your company' },
    takePhoto: { es: 'Tomar foto', fr: 'Prendre une photo', en: 'Take photo' },
    chooseFile: { es: 'Elegir archivo', fr: 'Choisir un fichier', en: 'Choose file' },
    uploading: { es: 'Extrayendo datos...', fr: 'Extraction des données...', en: 'Extracting data...' },
    extracted: { es: 'Datos extraídos correctamente', fr: 'Données extraites avec succès', en: 'Data extracted successfully' },
    remove: { es: 'Eliminar', fr: 'Supprimer', en: 'Remove' },
    formats: { es: 'PDF, JPG, PNG — máx. 10 MB', fr: 'PDF, JPG, PNG — max. 10 Mo', en: 'PDF, JPG, PNG — max 10 MB' },
  };
  const t = (key: string) => labels[key]?.[lang] ?? labels[key]?.es ?? key;

  const handleTakePhoto = useCallback(async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission required', 'Camera access is needed');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      quality: 0.8,
    });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      wizard.uploadDocument(asset.uri, asset.mimeType || 'image/jpeg');
    }
  }, [wizard]);

  const handleChooseFile = useCallback(async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ['application/pdf', 'image/jpeg', 'image/png'],
        copyToCacheDirectory: true,
      });
      if (!result.canceled && result.assets[0]) {
        const asset = result.assets[0];
        wizard.uploadDocument(asset.uri, asset.mimeType || 'application/pdf');
      }
    } catch {
      // User cancelled
    }
  }, [wizard]);

  // Uploading state
  if (wizard.isUploading) {
    return (
      <View style={s.centered}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text variant="bodyMedium" style={{ color: colors.outline, marginTop: 12 }}>{t('uploading')}</Text>
      </View>
    );
  }

  // Document extracted — show preview
  if (wizard.documentPreview) {
    const ext = wizard.documentPreview.extraction || {};
    const empresa = ext.empresa || ext;
    return (
      <View style={{ padding: 16, gap: 16 }}>
        {/* Success */}
        <View style={[s.successBanner, { backgroundColor: '#E8F5E9' }]}>
          <MaterialCommunityIcons name="check-circle" size={22} color="#2E7D32" />
          <Text variant="bodyMedium" style={{ color: '#2E7D32', marginLeft: 8, flex: 1, fontWeight: '600' }}>
            {t('extracted')}
          </Text>
        </View>

        {/* Extracted data preview */}
        <View style={[s.previewCard, { backgroundColor: colors.surface, borderColor: colors.outlineVariant }]}>
          {empresa.legal_name && (
            <View style={s.previewRow}>
              <Text variant="labelSmall" style={{ color: colors.outline }}>Nombre</Text>
              <Text variant="bodyMedium" style={{ fontWeight: '600' }}>{empresa.legal_name}</Text>
            </View>
          )}
          {empresa.nif && (
            <View style={s.previewRow}>
              <Text variant="labelSmall" style={{ color: colors.outline }}>NIF</Text>
              <Text variant="bodyMedium">{empresa.nif}</Text>
            </View>
          )}
          {empresa.numero_registro && (
            <View style={s.previewRow}>
              <Text variant="labelSmall" style={{ color: colors.outline }}>Registro</Text>
              <Text variant="bodyMedium">{empresa.numero_registro}</Text>
            </View>
          )}
          {empresa.localidad && (
            <View style={s.previewRow}>
              <Text variant="labelSmall" style={{ color: colors.outline }}>Localidad</Text>
              <Text variant="bodyMedium">{empresa.localidad}</Text>
            </View>
          )}
          {wizard.documentPreview.confidence != null && (
            <View style={s.previewRow}>
              <Text variant="labelSmall" style={{ color: colors.outline }}>Confidence</Text>
              <Text variant="bodyMedium">{Math.round(wizard.documentPreview.confidence * 100)}%</Text>
            </View>
          )}
        </View>

        {/* Remove button */}
        <Button mode="outlined" icon="delete-outline" onPress={wizard.deleteDocument} textColor={colors.error}>
          {t('remove')}
        </Button>
      </View>
    );
  }

  // Default: upload zone
  return (
    <View style={{ flex: 1, padding: 24, gap: 16 }}>
      <View style={{ alignItems: 'center', gap: 8 }}>
        <MaterialCommunityIcons name="file-document-outline" size={56} color={colors.primary} />
        <Text variant="titleSmall" style={{ fontWeight: '600', textAlign: 'center' }}>{t('title')}</Text>
        <Text variant="bodySmall" style={{ color: colors.outline, textAlign: 'center' }}>{t('desc')}</Text>
        <Text variant="labelSmall" style={{ color: colors.outline }}>{t('formats')}</Text>
      </View>

      <View style={{ gap: 10, marginTop: 16 }}>
        <Button mode="contained" icon="camera" onPress={handleTakePhoto}>
          {t('takePhoto')}
        </Button>
        <Button mode="outlined" icon="file-upload-outline" onPress={handleChooseFile}>
          {t('chooseFile')}
        </Button>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  successBanner: { flexDirection: 'row', alignItems: 'center', padding: 12, borderRadius: 8 },
  previewCard: { padding: 16, borderRadius: 12, borderWidth: 1, gap: 10 },
  previewRow: { gap: 2 },
});
