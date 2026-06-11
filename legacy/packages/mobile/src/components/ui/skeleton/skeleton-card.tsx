/**
 * SkeletonCard — placeholder card with header + 3 description lines.
 * Matches the rough envelope of payment-detail / ticket-detail cards.
 */

import { StyleSheet, View } from 'react-native';

import { useAppTheme } from '@core/theme';
import { SkeletonText } from './skeleton-text';

interface Props {
  /** Number of description lines (defaults to 3). */
  lines?: number;
}

export function SkeletonCard({ lines = 3 }: Props) {
  const { colors, spacing, borderRadius } = useAppTheme();
  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.card,
        {
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          padding: spacing.md,
        },
      ]}
    >
      <SkeletonText width="55%" height={18} radius={4} marginBottom={12} />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonText
          key={i}
          width={i === lines - 1 ? '40%' : '95%'}
          height={12}
          radius={4}
          marginBottom={i === lines - 1 ? 0 : 6}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {},
});
