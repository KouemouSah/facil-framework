import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme, type AppTheme } from '@core/theme';
import type { TicketStatus } from '../types/support.types';

interface Props {
  status: TicketStatus;
  compact?: boolean;
}

type BadgeColors = { bg: string; text: string };

function getColors(
  status: TicketStatus,
  colors: AppTheme['colors'],
  isDark: boolean,
): BadgeColors {
  if (isDark) {
    switch (status) {
      case 'open':
        return { bg: '#0D2440', text: '#90CAF9' };
      case 'in_progress':
        return { bg: '#3E2200', text: '#FFB74D' };
      case 'pending_user':
        return { bg: '#3E2C00', text: '#FFCC80' };
      case 'resolved':
        return { bg: '#1B3320', text: '#A5D6A7' };
      case 'closed':
        return { bg: colors.surfaceVariant, text: colors.outline };
      default:
        return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
    }
  }
  switch (status) {
    case 'open':
      return { bg: '#E3F2FD', text: '#0D3D6B' };
    case 'in_progress':
      return { bg: '#FFF3E0', text: '#7A2E00' };
    case 'pending_user':
      return { bg: '#FFF8E1', text: '#7A4F00' };
    case 'resolved':
      return { bg: '#E8F5E9', text: '#1B5E20' };
    case 'closed':
      return { bg: colors.surfaceVariant, text: colors.outline };
    default:
      return { bg: colors.surfaceVariant, text: colors.onSurfaceVariant };
  }
}

export function TicketStatusBadge({ status, compact }: Props) {
  const { colors, isDark } = useAppTheme();
  const { t } = useTranslation();
  const badge = getColors(status, colors, isDark);
  const label = t(`support.status.${status}`, { defaultValue: status });
  return (
    <View
      style={[
        styles.badge,
        compact ? styles.compact : styles.normal,
        { backgroundColor: badge.bg },
      ]}
    >
      <Text
        numberOfLines={1}
        style={[compact ? styles.textCompact : styles.textNormal, { color: badge.text }]}
      >
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { alignSelf: 'flex-start', borderRadius: 20 },
  normal: { paddingHorizontal: 12, paddingVertical: 5 },
  compact: { paddingHorizontal: 8, paddingVertical: 3 },
  textNormal: { fontSize: 12, fontWeight: '600', lineHeight: 16 },
  textCompact: { fontSize: 10, fontWeight: '600', lineHeight: 14 },
});
