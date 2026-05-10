import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme, type AppTheme } from '@core/theme';
import type { TicketPriority } from '../types/support.types';

interface Props {
  priority: TicketPriority;
  compact?: boolean;
}

function getColors(
  priority: TicketPriority,
  colors: AppTheme['colors'],
  isDark: boolean,
) {
  if (isDark) {
    switch (priority) {
      case 'urgent':
        return { bg: '#3E1A1A', text: '#EF9A9A' };
      case 'high':
        return { bg: '#3E2C00', text: '#FFCC80' };
      case 'normal':
        return { bg: colors.surfaceVariant, text: colors.outline };
      case 'low':
        return { bg: '#1B3320', text: '#A5D6A7' };
    }
  }
  switch (priority) {
    case 'urgent':
      return { bg: '#FFEBEE', text: '#8B1A1A' };
    case 'high':
      return { bg: '#FFF8E1', text: '#7A4F00' };
    case 'normal':
      return { bg: colors.surfaceVariant, text: colors.outline };
    case 'low':
      return { bg: '#E8F5E9', text: '#1B5E20' };
  }
}

export function TicketPriorityBadge({ priority, compact }: Props) {
  const { colors, isDark } = useAppTheme();
  const { t } = useTranslation();
  const badge = getColors(priority, colors, isDark);
  return (
    <View
      style={[
        styles.badge,
        compact ? styles.compact : styles.normal,
        { backgroundColor: badge.bg },
      ]}
    >
      <Text
        style={[compact ? styles.textCompact : styles.textNormal, { color: badge.text }]}
      >
        {t(`support.priority.${priority}`, { defaultValue: priority })}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', borderRadius: 12 },
  normal: { paddingHorizontal: 10, paddingVertical: 3 },
  compact: { paddingHorizontal: 7, paddingVertical: 2 },
  textNormal: { fontSize: 11, fontWeight: '600' },
  textCompact: { fontSize: 9, fontWeight: '600' },
});
