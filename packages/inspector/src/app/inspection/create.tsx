/**
 * Create Inspection Screen
 *
 * Pre-filled from license verification.
 * Captures GPS on mount, agent adds notes, confirms.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View, ScrollView, Alert } from 'react-native';
import { Button, Divider, Text, TextInput } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { useLocation } from '@core/hooks/use-location';
import { extractApiError } from '@core/api/errors';
import { generateIdempotencyKey } from '@core/api/idempotency';
import { useCreateInspection, useUpdateInspection } from '@modules/inspections/services/inspections-hooks';

export default function CreateInspectionScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{
    license_id: string;
    company_id: string;
    company_name: string;
  }>();

  const { location, isLoading: gpsLoading, requestLocation } = useLocation();

  // P4: Stable Idempotency-Key for the lifetime of this screen.
  // If the user retries (network glitch), the same key is reused → backend replay.
  const idempotencyKeyRef = useRef<string>(generateIdempotencyKey());
  const createInspection = useCreateInspection(idempotencyKeyRef.current);

  const [notes, setNotes] = useState('');
  const [error, setError] = useState('');

  // Auto-capture GPS on mount
  useEffect(() => {
    requestLocation();
  }, [requestLocation]);

  const handleCreate = useCallback(async () => {
    if (!params.license_id || !params.company_id) {
      setError(t('inspection.licenseDataIncomplete'));
      return;
    }

    setError('');
    try {
      const result = await createInspection.mutateAsync({
        license_id: params.license_id,
        company_id: params.company_id,
        notes: notes.trim() || undefined,
      });

      // Send GPS coordinates via update (create endpoint doesn't accept GPS)
      if (location) {
        try {
          const { inspectionsApi } = await import('@modules/inspections/services/inspections-api');
          await inspectionsApi.update(result.id, {
            gps_latitude: location.latitude,
            gps_longitude: location.longitude,
            gps_accuracy: location.accuracy ?? undefined,
          });
        } catch {
          // GPS update failure is non-blocking — inspection was created successfully
        }
      }

      // Navigate to the new inspection detail
      router.replace(`/inspection/${result.id}` as never);
    } catch (err) {
      const apiError = extractApiError(err);
      setError(apiError.message);
    }
  }, [params, notes, location, createInspection]);

  const handleCancel = useCallback(() => {
    if (notes.trim()) {
      Alert.alert(
        t('common.confirm'),
        t('inspection.discardInspection'),
        [
          { text: t('common.cancel'), style: 'cancel' },
          { text: t('common.confirm'), onPress: () => router.back(), style: 'destructive' },
        ],
      );
    } else {
      router.back();
    }
  }, [notes, t]);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={handleCancel} textColor={colors.primary}>
            {t('common.cancel')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('inspection.new')}
          </Text>
          <View style={{ width: 80 }} />
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {/* Company Info */}
        <View style={[styles.infoCard, { backgroundColor: colors.surface }]}>
          <MaterialCommunityIcons name="domain" size={24} color={colors.primary} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text variant="titleSmall" style={{ color: colors.onSurface }}>
              {params.company_name || '-'}
            </Text>
          </View>
        </View>

        {/* GPS Status */}
        <View style={[styles.infoCard, { backgroundColor: colors.surface }]}>
          <MaterialCommunityIcons
            name={location ? 'map-marker-check' : gpsLoading ? 'map-marker-question' : 'map-marker-off'}
            size={24}
            color={location ? colors.primary : colors.onSurfaceVariant}
          />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text variant="bodyMedium" style={{ color: colors.onSurface }}>
              {t('inspection.gps')}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {gpsLoading
                ? t('inspection.obtainingLocation')
                : location
                  ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)} (\u00B1${Math.round(location.accuracy ?? 0)}m)`
                  : t('inspection.gpsUnavailable')}
            </Text>
          </View>
          {!location && !gpsLoading && (
            <Button compact onPress={requestLocation} textColor={colors.primary}>
              {t('inspection.retryGps')}
            </Button>
          )}
        </View>

        <Divider style={{ marginVertical: 8 }} />

        {/* Notes */}
        <View style={styles.notesSection}>
          <Text variant="labelLarge" style={{ color: colors.onSurfaceVariant, marginBottom: 8 }}>
            {t('inspection.notes')}
          </Text>
          <TextInput
            mode="outlined"
            value={notes}
            onChangeText={setNotes}
            placeholder={t('inspection.notesPlaceholder')}
            multiline
            numberOfLines={4}
            maxLength={2000}
            style={styles.notesInput}
          />
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, textAlign: 'right' }}>
            {notes.length}/2000
          </Text>
        </View>

        {error ? (
          <Text variant="bodyMedium" style={{ color: colors.error, paddingHorizontal: 16, marginBottom: 8 }}>
            {error}
          </Text>
        ) : null}

        {/* Create Button */}
        <Button
          mode="contained"
          icon="clipboard-check"
          onPress={handleCreate}
          loading={createInspection.isPending}
          disabled={createInspection.isPending || !params.license_id}
          style={styles.createButton}
          contentStyle={{ paddingVertical: 6 }}
        >
          {t('inspection.new')}
        </Button>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 8 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  content: { paddingBottom: 32 },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 8,
    padding: 12,
    borderRadius: 8,
  },
  notesSection: { paddingHorizontal: 16, marginTop: 8 },
  notesInput: { backgroundColor: 'transparent' },
  createButton: { marginHorizontal: 16, marginTop: 16, borderRadius: 8 },
});
