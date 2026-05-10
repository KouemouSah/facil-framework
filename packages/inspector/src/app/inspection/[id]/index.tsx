/**
 * Inspection Detail Screen — Full workflow view
 * Android native: sections with dividers, no elevated cards
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Divider, Switch, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { formatDate, formatCurrency } from '@core/utils/format';
import { StatusBadge } from '@components/ui/status-badge';
import { SkeletonInspectionDetail } from '@components/ui/skeleton';
import { useInspectionDetail, useUpdateInspection, useUploadPhoto } from '@modules/inspections/services/inspections-hooks';
import { ActionButtons } from '@modules/inspections/components/action-buttons';
import { PhotoGallery } from '@modules/camera/components/photo-gallery';
import type { PhotoCapture } from '@modules/camera/services/photo-service';

export default function InspectionDetailScreen() {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const { data: inspection, isLoading } = useInspectionDetail(id ?? '');
  const updateMutation = useUpdateInspection(id ?? '');
  const uploadPhotoMutation = useUploadPhoto(id ?? '');

  const [localPhotos, setLocalPhotos] = useState<PhotoCapture[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Upload photos immediately after capture (prevent data loss in field)
  const handleLocalPhotosChange = useCallback(async (newPhotos: PhotoCapture[]) => {
    // Find newly added photos (diff between new and current)
    const added = newPhotos.filter(
      (p) => !localPhotos.some((lp) => lp.uri === p.uri),
    );

    setLocalPhotos(newPhotos);

    // Upload each new photo immediately
    for (const photo of added) {
      setIsUploading(true);
      try {
        const formData = new FormData();
        const filename = `inspection-${Date.now()}.jpg`;
        formData.append('file', {
          uri: photo.uri,
          type: 'image/jpeg',
          name: filename,
        } as unknown as Blob);

        await uploadPhotoMutation.mutateAsync({ formData });
        // Remove from local after successful upload
        setLocalPhotos((prev) => prev.filter((p) => p.uri !== photo.uri));
      } catch {
        // Keep in localPhotos so user can retry — don't silently lose
      } finally {
        setIsUploading(false);
      }
    }
  }, [localPhotos, uploadPhotoMutation]);

  const isEditable = inspection?.status === 'in_progress';

  // Auto-save on blur with debounce
  const handleFieldUpdate = useCallback(
    (field: string, value: unknown) => {
      if (!id) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        updateMutation.mutate({ [field]: value });
      }, 1500);
    },
    [id, updateMutation],
  );

  if (isLoading || !inspection) return <SkeletonInspectionDetail />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <StatusBadge
            status={inspection.result ?? inspection.status}
            label={t(`${inspection.result ? 'result' : 'status'}.${inspection.result ?? inspection.status}`)}
            size="medium"
          />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Company Section */}
        <View style={styles.section}>
          <View style={styles.companyRow}>
            <MaterialCommunityIcons name="domain" size={20} color={colors.primary} />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text variant="titleMedium" style={{ color: colors.onSurface }}>
                {inspection.company_name ?? '—'}
              </Text>
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {inspection.company_nif ?? '—'} • {formatDate(inspection.inspection_date)} • {inspection.entity_code}
              </Text>
            </View>
          </View>
        </View>
        <Divider />

        {/* Activity Section */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('inspection.activity')}
          </Text>
          <View style={styles.switchRow}>
            <Text variant="bodyMedium" style={{ flex: 1, color: colors.onSurface }}>
              {t('inspection.activityConforme')}
            </Text>
            <Switch
              value={inspection.activity_conforme ?? false}
              onValueChange={(v) => {
                if (isEditable) handleFieldUpdate('activity_conforme', v);
              }}
              disabled={!isEditable}
              color={custom.status.conforme}
            />
          </View>
          {isEditable ? (
            <>
              <TextInput
                mode="flat"
                label={t('inspection.activityDeclared')}
                defaultValue={inspection.activity_declared ?? ''}
                onEndEditing={(e) => handleFieldUpdate('activity_declared', e.nativeEvent.text)}
                maxLength={200}
                dense
                style={styles.flatInput}
              />
              <TextInput
                mode="flat"
                label={t('inspection.activityObserved')}
                defaultValue={inspection.activity_observed ?? ''}
                onEndEditing={(e) => handleFieldUpdate('activity_observed', e.nativeEvent.text)}
                maxLength={200}
                dense
                style={styles.flatInput}
              />
            </>
          ) : (
            <>
              {inspection.activity_declared && (
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, paddingVertical: 4 }}>
                  {t('inspection.declared')}: {inspection.activity_declared}
                </Text>
              )}
              {inspection.activity_observed && (
                <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, paddingVertical: 4 }}>
                  {t('inspection.observed')}: {inspection.activity_observed}
                </Text>
              )}
            </>
          )}
        </View>
        <Divider />

        {/* Photos Section */}
        <View style={styles.section}>
          <PhotoGallery
            photos={inspection.photos}
            localPhotos={localPhotos}
            onLocalPhotosChange={handleLocalPhotosChange}
            readonly={!isEditable}
          />
          {isUploading && (
            <Text variant="bodySmall" style={{ color: colors.primary, paddingHorizontal: 16 }}>
              {t('common.loading')}
            </Text>
          )}
        </View>
        <Divider />

        {/* GPS Section */}
        <View style={styles.section}>
          <View style={styles.gpsRow}>
            <MaterialCommunityIcons
              name={inspection.gps_latitude ? 'map-marker-check' : 'map-marker-off'}
              size={18}
              color={inspection.gps_latitude ? colors.primary : colors.onSurfaceVariant}
            />
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginLeft: 6 }}>
              {inspection.gps_latitude
                ? `${Number(inspection.gps_latitude).toFixed(5)}, ${Number(inspection.gps_longitude).toFixed(5)} (±${Math.round(Number(inspection.gps_accuracy ?? 0))}m)`
                : t('inspection.gpsNotRecorded')}
            </Text>
          </View>
        </View>
        <Divider />

        {/* Notes Section */}
        <View style={styles.section}>
          <Text variant="labelLarge" style={[styles.sectionTitle, { color: colors.onSurfaceVariant }]}>
            {t('inspection.notes')}
          </Text>
          {isEditable ? (
            <TextInput
              mode="flat"
              defaultValue={inspection.notes ?? ''}
              onEndEditing={(e) => handleFieldUpdate('notes', e.nativeEvent.text)}
              multiline
              numberOfLines={3}
              maxLength={2000}
              placeholder={t('inspection.addNotesPlaceholder')}
              style={styles.flatInput}
            />
          ) : (
            <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
              {inspection.notes ?? '—'}
            </Text>
          )}
        </View>
        <Divider />

        {/* Obligations Summary */}
        <View style={styles.section}>
          <View style={styles.obligRow}>
            <Text variant="labelLarge" style={{ color: colors.onSurfaceVariant }}>
              {t('inspection.obligations')}
            </Text>
            <Text variant="titleSmall" style={{ color: inspection.unpaid_obligations_count > 0 ? custom.status.nonConforme : custom.status.conforme }}>
              {inspection.unpaid_obligations_count} • {formatCurrency(inspection.unpaid_obligations_amount)}
            </Text>
          </View>
        </View>
        <Divider />

        {/* MED info if applicable */}
        {inspection.mise_en_demeure_issued && (
          <>
            <View style={[styles.section, { backgroundColor: `${custom.status.miseEnDemeure}08` }]}>
              <View style={styles.medRow}>
                <MaterialCommunityIcons name="alert-circle" size={18} color={custom.status.miseEnDemeure} />
                <View style={{ flex: 1, marginLeft: 8 }}>
                  <Text variant="labelMedium" style={{ color: custom.status.miseEnDemeure }}>
                    {t('med.title')}
                  </Text>
                  {inspection.mise_en_demeure_deadline && (
                    <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                      Limite: {formatDate(inspection.mise_en_demeure_deadline, 'dd/MM/yyyy HH:mm')}
                    </Text>
                  )}
                </View>
              </View>
            </View>
            <Divider />
          </>
        )}

        {/* Seal info if applicable */}
        {inspection.seal_applied && (
          <>
            <View style={[styles.section, { backgroundColor: `${custom.status.sealApproved}08` }]}>
              <View style={styles.medRow}>
                <MaterialCommunityIcons name="lock" size={18} color={custom.status.sealApproved} />
                <View style={{ flex: 1, marginLeft: 8 }}>
                  <Text variant="labelMedium" style={{ color: custom.status.sealApproved }}>
                    {t('inspection.sealLabel')}: {t(`seal.reasons.${inspection.seal_reason}`)}
                  </Text>
                  <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                    {inspection.seal_notes}
                  </Text>
                </View>
              </View>
            </View>
            <Divider />
          </>
        )}

        {/* Action Buttons */}
        <ActionButtons inspection={inspection} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 8 },
  scrollContent: { paddingBottom: 32 },
  section: { paddingHorizontal: 16, paddingVertical: 12 },
  sectionTitle: { fontWeight: '600', marginBottom: 8 },
  companyRow: { flexDirection: 'row', alignItems: 'center' },
  switchRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  flatInput: { backgroundColor: 'transparent', marginBottom: 4 },
  gpsRow: { flexDirection: 'row', alignItems: 'center' },
  obligRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  medRow: { flexDirection: 'row', alignItems: 'center' },
});
