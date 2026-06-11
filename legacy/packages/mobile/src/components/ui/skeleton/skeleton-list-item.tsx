/**
 * SkeletonListItem — placeholder row matching the layout of `RequestListItem`,
 * `PaymentListItem`, `TicketListItem` (10dp dot + 2 text lines + chevron, with
 * 12dp vertical padding → 64dp tall). Used while the FlatList is loading.
 */

import { StyleSheet, View } from 'react-native';

import { useAppTheme } from '@core/theme';
import { SkeletonText } from './skeleton-text';

export function SkeletonListItem() {
  const { colors, spacing } = useAppTheme();
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.row,
        { paddingHorizontal: spacing.md, paddingVertical: 12 },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: colors.surfaceVariant }]} />
      <View style={styles.content}>
        <SkeletonText width="65%" height={15} radius={4} marginBottom={6} />
        <SkeletonText width="40%" height={12} radius={4} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', height: 64 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  content: { flex: 1, gap: 2 },
});
