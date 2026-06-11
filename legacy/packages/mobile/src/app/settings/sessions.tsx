/**
 * Active Sessions Screen
 *
 * Lists all active sessions for the current user.
 * Allows signing out from all other devices.
 *
 * Uses GET /auth/sessions and POST /auth/logout with all_sessions flag.
 */

import { useCallback, useState } from 'react';
import { StyleSheet, View, FlatList, Alert } from 'react-native';
import {
  Text,
  Surface,
  Button,
  Chip,
  Snackbar,
  Divider,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { SkeletonListItem } from '@components/ui/skeleton';
import { apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { useSessions } from '@modules/auth/services/auth-hooks';
import type { SessionInfo } from '@core/config/types';

// Use locale-aware formatRelativeTime from core utils
import { formatRelativeTime } from '@core/utils/format';

function getDeviceIcon(device: string): string {
  const d = device.toLowerCase();
  if (d.includes('mobile') || d.includes('phone')) return 'cellphone';
  if (d.includes('tablet')) return 'tablet';
  return 'monitor';
}

function SessionCard({
  session,
  colors,
  spacing,
  borderRadius,
  t,
}: {
  session: SessionInfo;
  colors: ReturnType<typeof useAppTheme>['colors'];
  spacing: ReturnType<typeof useAppTheme>['spacing'];
  borderRadius: ReturnType<typeof useAppTheme>['borderRadius'];
  t: ReturnType<typeof useTranslation>['t'];
}) {
  return (
    <Surface
      style={[
        styles.sessionCard,
        {
          padding: spacing.md,
          borderRadius: borderRadius.md,
          backgroundColor: colors.surface,
          marginBottom: spacing.sm,
        },
      ]}
      elevation={1}
    >
      <View style={styles.sessionRow}>
        <MaterialCommunityIcons
          name={getDeviceIcon(session.device) as keyof typeof MaterialCommunityIcons.glyphMap}
          size={28}
          color={session.is_current ? colors.primary : colors.outline}
        />
        <View style={styles.sessionInfo}>
          <View style={styles.sessionHeader}>
            <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
              {session.device} — {session.browser}
            </Text>
            {session.is_current && (
              <Chip
                compact
                style={{ backgroundColor: colors.primaryContainer, height: 24 }}
                textStyle={{ color: colors.onPrimaryContainer, fontSize: 10 }}
              >
                {t('profile.currentSession')}
              </Chip>
            )}
          </View>
          {session.location && (
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {session.location}
            </Text>
          )}
          <Text variant="bodySmall" style={{ color: colors.outline }}>
            {t('profile.lastActivity')}: {formatRelativeTime(session.last_activity)}
          </Text>
        </View>
      </View>
    </Surface>
  );
}

export default function SessionsScreen() {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const { data, isLoading, refetch, isRefetching } = useSessions();
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const handleSignOutAll = useCallback(() => {
    Alert.alert(
      t('profile.signOutAllOtherDevices'),
      t('profile.signOutAllOtherDevicesDesc'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('auth.signOut'),
          style: 'destructive',
          onPress: async () => {
            try {
              // Revoke all OTHER sessions (not the current one)
              // Call logout API directly — do NOT clear local tokens
              await apiPost(API_ENDPOINTS.auth.logout, {
                all_sessions: true,
              });
              setSnackbar(t('profile.otherSessionsRevoked'));
              refetch();
            } catch {
              setSnackbar(t('common.errorOccurred'));
            }
          },
        },
      ],
    );
  }, [t, refetch]);

  if (isLoading) {
    return (
      <View>
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonListItem key={`sk-${i}`} />
        ))}
      </View>
    );
  }

  const sessions = data?.sessions ?? [];
  const otherSessionsCount = sessions.filter((s) => !s.is_current).length;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <FlatList
        data={sessions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ padding: spacing.md }}
        refreshing={isRefetching}
        onRefresh={refetch}
        ListHeaderComponent={
          <View style={{ marginBottom: spacing.md }}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('profile.sessionsDescription', { count: sessions.length })}
            </Text>
          </View>
        }
        renderItem={({ item }) => (
          <SessionCard
            session={item}
            colors={colors}
            spacing={spacing}
            borderRadius={borderRadius}
            t={t}
          />
        )}
        ListFooterComponent={
          otherSessionsCount > 0 ? (
            <View style={{ marginTop: spacing.md }}>
              <Divider style={{ marginBottom: spacing.md }} />
              <Button
                mode="outlined"
                icon="logout"
                onPress={handleSignOutAll}
                textColor={colors.error}
                style={{ borderColor: colors.error }}
              >
                {t('profile.signOutAllOtherDevices')} ({otherSessionsCount})
              </Button>
            </View>
          ) : null
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <MaterialCommunityIcons name="devices" size={48} color={colors.outline} />
            <Text variant="bodyLarge" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>
              {t('profile.noOtherSessions')}
            </Text>
          </View>
        }
      />

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  sessionCard: { overflow: 'hidden' },
  sessionRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  sessionInfo: { flex: 1, gap: 2 },
  sessionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  emptyContainer: { alignItems: 'center', paddingVertical: 48 },
});
