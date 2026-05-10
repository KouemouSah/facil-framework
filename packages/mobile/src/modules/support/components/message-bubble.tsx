import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import { formatRelativeTime } from '@core/utils/format';
import type { SupportMessage } from '../types/support.types';

interface Props {
  message: SupportMessage;
  /** True when the message was authored by the current user — right-aligned bubble. */
  isMine: boolean;
}

export function MessageBubble({ message, isMine }: Props) {
  const { colors, isDark } = useAppTheme();

  const bg = isMine
    ? colors.primaryContainer
    : isDark
      ? colors.surfaceVariant
      : '#F1F3F4';
  const fg = isMine ? colors.onPrimaryContainer : colors.onSurface;

  return (
    <View
      style={[
        styles.row,
        isMine ? styles.rowRight : styles.rowLeft,
      ]}
    >
      <View
        style={[
          styles.bubble,
          isMine ? styles.bubbleRight : styles.bubbleLeft,
          { backgroundColor: bg },
        ]}
      >
        {!isMine && message.sender_name ? (
          <Text style={[styles.author, { color: colors.outline }]} numberOfLines={1}>
            {message.sender_name}
          </Text>
        ) : null}
        <Text style={[styles.content, { color: fg }]}>{message.content}</Text>
        <Text style={[styles.time, { color: colors.outline }]}>
          {formatRelativeTime(message.created_at)}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { width: '100%', flexDirection: 'row', marginVertical: 4, paddingHorizontal: 12 },
  rowLeft: { justifyContent: 'flex-start' },
  rowRight: { justifyContent: 'flex-end' },
  bubble: {
    maxWidth: '80%',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 14,
    gap: 2,
  },
  bubbleLeft: { borderTopLeftRadius: 4 },
  bubbleRight: { borderTopRightRadius: 4 },
  author: { fontSize: 11, fontWeight: '600', marginBottom: 2 },
  content: { fontSize: 14, lineHeight: 20 },
  time: { fontSize: 10, marginTop: 4, alignSelf: 'flex-end' },
});
