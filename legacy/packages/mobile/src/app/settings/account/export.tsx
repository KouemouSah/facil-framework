/**
 * Settings → Account → Export my data (RGPD art. 20).
 *
 * Calls `GET /users/profile/export` and writes the JSON response to a
 * temporary file in the app's document directory, then opens the OS share
 * sheet so the user can save it to Drive / Files / send to themselves.
 *
 * V1 caveats:
 *   - Backend caps the export window to 90 days for high-cardinality tables.
 *   - The download is fully synchronous (no async job). Acceptable for V1
 *     given the 90-day cap; revisit when a power user reports timeouts.
 */

import { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Button,
  IconButton,
  Surface,
  Text,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { documentDirectory, writeAsStringAsync } from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import apiClient from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { logger } from '@core/logging/logger';

function AccountExportContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [busy, setBusy] = useState(false);

  const handleExport = useCallback(async () => {
    setBusy(true);
    try {
      // Pull the JSON payload — backend already attaches a Content-Disposition
      // header but axios surfaces only the body for us, so we re-stringify.
      // The default 30s axios timeout would cut a power user with hundreds of
      // payments mid-aggregation; bump to 60s for this endpoint specifically.
      const response = await apiClient.get(API_ENDPOINTS.users.exportData, {
        responseType: 'json',
        timeout: 60_000,
      });

      const filename = `facil-export-${Date.now()}.json`;
      const uri = `${documentDirectory}${filename}`;

      await writeAsStringAsync(uri, JSON.stringify(response.data, null, 2));

      const sharingAvailable = await Sharing.isAvailableAsync();
      if (!sharingAvailable) {
        Alert.alert(
          t('settings.exportData.title', { defaultValue: 'Export my data' }),
          t('settings.exportData.savedTo', { uri, defaultValue: `Saved to ${uri}` }),
        );
        return;
      }

      await Sharing.shareAsync(uri, {
        mimeType: 'application/json',
        dialogTitle: t('settings.exportData.shareTitle', {
          defaultValue: 'Share my Facil data export',
        }),
      });
    } catch (err) {
      logger.error('rgpd-export', err, 'Data export failed');
      Alert.alert(
        t('common.error'),
        t('settings.exportData.errorBody', {
          defaultValue: 'Could not export your data. Please try again.',
        }),
      );
    } finally {
      setBusy(false);
    }
  }, [t]);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[
          styles.topBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
        ]}
      >
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {t('settings.exportData.title', { defaultValue: 'Export my data' })}
        </Text>
      </View>

      <ScrollView contentContainerStyle={[styles.scroll, { padding: spacing.md }]}>
        <Surface
          style={[
            styles.card,
            {
              padding: spacing.lg,
              borderRadius: borderRadius.md,
              backgroundColor: colors.surface,
              gap: spacing.sm,
            },
          ]}
          elevation={0}
        >
          <View style={styles.headerRow}>
            <MaterialCommunityIcons name="download-outline" size={28} color={colors.primary} />
            <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '700' }}>
              {t('settings.exportData.subtitle', {
                defaultValue: 'Right to data portability — RGPD art. 20',
              })}
            </Text>
          </View>
          <Text style={{ color: colors.onSurfaceVariant }}>
            {t('settings.exportData.description', {
              defaultValue:
                'Download a JSON file with your profile, your payments and your service requests for the last 90 days. You can save it to Drive, your files, or send it to yourself.',
            })}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.outline, marginTop: 4 }}>
            {t('settings.exportData.note', {
              defaultValue:
                'No documents (PDF / images) are included — only their metadata.',
            })}
          </Text>
        </Surface>

        <Button
          mode="contained"
          icon="cloud-download-outline"
          loading={busy}
          disabled={busy}
          onPress={handleExport}
          contentStyle={{ paddingVertical: 6 }}
          style={{ marginTop: spacing.md, borderRadius: borderRadius.sm }}
        >
          {t('settings.exportData.cta', { defaultValue: 'Download my data' })}
        </Button>

        {busy ? (
          <View style={{ alignItems: 'center', marginTop: 16 }}>
            <ActivityIndicator color={colors.primary} />
            <Text style={{ color: colors.outline, marginTop: 8 }}>
              {t('settings.exportData.preparing', { defaultValue: 'Preparing your data...' })}
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  scroll: { flexGrow: 1 },
  card: { width: '100%' },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});

export default function AccountExportScreen() {
  return (
    <AuthGuard>
      <AccountExportContent />
    </AuthGuard>
  );
}
