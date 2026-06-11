/**
 * ReadinessBanner — pre-flight indicator for a workflow.
 *
 * Reads `useVaultReadinessForWorkflow(workflowCode)`, summarises score +
 * missing/expiring counts, and offers a tap shortcut to the vault.
 *
 * Render policy:
 *   - score === 100 → success card "Tous vos documents sont prêts"
 *   - 80 ≤ score < 100 → amber card "X / Y prêts"
 *   - score < 80 → red card with explicit missing list
 *   - loading / no data → render nothing (avoid skeleton flash on a screen
 *     where the banner is decorative, not load-bearing)
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { useVaultReadinessForWorkflow } from '../services/vault-hooks';

interface ReadinessBannerProps {
  workflowCode: string;
  onPress?: () => void;
}

export function ReadinessBanner({ workflowCode, onPress }: ReadinessBannerProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const readiness = useVaultReadinessForWorkflow(workflowCode);
  const data = readiness.data;

  if (!data) return null;

  const score = data.readiness_score;
  const ready = (data.ready ?? []).length;
  const total = data.total_required ?? ready + (data.missing ?? []).length;
  const missing = (data.missing ?? []).length;
  const expiring = (data.expiring ?? []).length;

  const variant: 'success' | 'warning' | 'error' =
    score >= 100 ? 'success' : score >= 80 ? 'warning' : 'error';

  const palette = {
    success: { bg: '#E8F5E9', fg: '#1B5E20', icon: 'check-circle' as const },
    warning: { bg: '#FFF8E1', fg: '#F57C00', icon: 'alert-circle-outline' as const },
    error: { bg: '#FFEBEE', fg: '#C62828', icon: 'alert' as const },
  }[variant];

  const titleKey =
    variant === 'success'
      ? 'vault.readiness.banner.titleAllReady'
      : 'vault.readiness.banner.titlePartial';
  const subtitleParts: string[] = [];
  if (missing > 0) subtitleParts.push(t('vault.readiness.banner.missing', { count: missing }));
  if (expiring > 0) subtitleParts.push(t('vault.readiness.banner.expiring', { count: expiring }));
  const subtitle = subtitleParts.join(' · ');

  return (
    <Pressable
      onPress={onPress}
      android_ripple={onPress ? { color: colors.surfaceVariant } : undefined}
      style={[styles.banner, { backgroundColor: palette.bg }]}
    >
      <MaterialCommunityIcons name={palette.icon} size={26} color={palette.fg} />
      <View style={styles.body}>
        <Text variant="titleSmall" style={{ color: palette.fg, fontWeight: '700' }}>
          {t(titleKey, { ready, total })}
        </Text>
        {subtitle ? (
          <Text variant="bodySmall" style={{ color: palette.fg }}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {onPress ? (
        <MaterialCommunityIcons name="chevron-right" size={22} color={palette.fg} />
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginHorizontal: 16,
    marginTop: 8,
    borderRadius: 12,
    gap: 12,
  },
  body: {
    flex: 1,
  },
});
