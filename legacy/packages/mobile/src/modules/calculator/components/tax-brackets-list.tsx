/**
 * IRPF tax brackets reference list.
 * Mirrors the web `taxBrackets` block in the IRPF tab.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

interface TaxBracketsListProps {
  brackets: readonly { range: string; rate: string; color: string }[];
  title: string;
}

export function TaxBracketsList({ brackets, title }: TaxBracketsListProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.surfaceVariant,
          borderRadius: borderRadius.md,
          padding: spacing.md,
          gap: spacing.xs,
        },
      ]}
    >
      <View style={[styles.titleRow, { marginBottom: spacing.xs }]}>
        <MaterialCommunityIcons
          name="information-outline"
          size={16}
          color={colors.primary}
        />
        <Text
          variant="labelMedium"
          style={{ color: colors.onSurface, fontWeight: '600', marginLeft: 6 }}
        >
          {title}
        </Text>
      </View>

      {brackets.map((b, idx) => (
        <View key={idx} style={styles.row}>
          <View
            style={[
              styles.dot,
              {
                backgroundColor: b.color,
              },
            ]}
          />
          <Text
            variant="bodySmall"
            style={{ color: colors.onSurfaceVariant, flex: 1, fontVariant: ['tabular-nums'] }}
          >
            {b.range}
          </Text>
          <View
            style={[
              styles.rateBadge,
              {
                backgroundColor: `${b.color}26`,
                borderColor: `${b.color}80`,
                borderRadius: borderRadius.full,
              },
            ]}
          >
            <Text
              variant="labelSmall"
              style={{ color: b.color, fontWeight: '700' }}
            >
              {b.rate}
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {},
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    gap: 10,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  rateBadge: {
    paddingHorizontal: 10,
    paddingVertical: 2,
    borderWidth: 1,
  },
});
