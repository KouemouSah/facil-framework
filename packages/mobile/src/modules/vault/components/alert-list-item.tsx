import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { AlertResponse } from '../types/vault.types';

interface AlertListItemProps {
  alert: AlertResponse;
  onPress: (alert: AlertResponse) => void;
  onLongPress?: (alert: AlertResponse) => void;
}

const SEVERITY_COLOR = {
  critical: '#D32F2F',
  warning: '#F57C00',
  info: '#1565C0',
} as const;

const SEVERITY_ICON = {
  critical: 'alert-circle' as const,
  warning: 'alert' as const,
  info: 'information' as const,
};

function pickI18nField<T extends Record<string, unknown>>(
  obj: T,
  basekey: string,
  lang: string,
): string {
  const candidate = obj[`${basekey}_${lang}`];
  if (typeof candidate === 'string' && candidate.length) return candidate;
  const fallback = obj[basekey];
  return typeof fallback === 'string' ? fallback : '';
}

function AlertListItemImpl({ alert, onPress, onLongPress }: AlertListItemProps) {
  const { t, i18n } = useTranslation();
  const { colors } = useAppTheme();
  const severity = alert.severity as keyof typeof SEVERITY_COLOR;
  const severityColor = SEVERITY_COLOR[severity] ?? SEVERITY_COLOR.info;
  const lang = (i18n.language ?? 'es').slice(0, 2);
  const title = pickI18nField(alert as unknown as Record<string, unknown>, 'title', lang);
  const message = pickI18nField(alert as unknown as Record<string, unknown>, 'message', lang);
  const isUnread = !alert.is_read;

  return (
    <Pressable
      onPress={() => onPress(alert)}
      onLongPress={onLongPress ? () => onLongPress(alert) : undefined}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[
        styles.row,
        { backgroundColor: isUnread ? colors.surfaceVariant : colors.surface },
      ]}
    >
      <MaterialCommunityIcons
        name={SEVERITY_ICON[severity] ?? SEVERITY_ICON.info}
        size={22}
        color={severityColor}
        style={styles.icon}
      />
      <View style={styles.body}>
        <Text
          variant="titleSmall"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: isUnread ? '700' : '500' }}
        >
          {title}
        </Text>
        <Text
          variant="bodySmall"
          numberOfLines={2}
          style={{ color: colors.onSurfaceVariant }}
        >
          {message || t('vault.alerts.fallbackMessage')}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 64,
    alignItems: 'center',
  },
  icon: {
    marginRight: 14,
  },
  body: {
    flex: 1,
  },
});

/** Memoized — vault alerts list re-renders on tab switch + cache refresh. */
export const AlertListItem = memo(AlertListItemImpl);
