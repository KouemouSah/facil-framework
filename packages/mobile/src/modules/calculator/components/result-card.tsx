/**
 * Generic result card for calculator tabs.
 *
 * Renders either:
 * - an empty state (icon + caption) when `result` is null/undefined
 * - the children block when a result is available
 *
 * Mirrors the web pattern (`<Card className={result ? 'border-primary/50' : ''}>`).
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text, Surface, Divider } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

interface ResultCardProps {
  title: string;
  subtitle?: string;
  hasResult: boolean;
  emptyIcon: keyof typeof MaterialCommunityIcons.glyphMap;
  emptyText: string;
  children?: React.ReactNode;
}

export function ResultCard({
  title,
  subtitle,
  hasResult,
  emptyIcon,
  emptyText,
  children,
}: ResultCardProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  return (
    <Surface
      elevation={1}
      style={[
        styles.card,
        {
          borderRadius: borderRadius.lg,
          backgroundColor: colors.surface,
          borderColor: hasResult ? colors.primary : colors.outlineVariant,
          borderWidth: hasResult ? 1 : StyleSheet.hairlineWidth,
        },
      ]}
    >
      <View style={[styles.header, { padding: spacing.md }]}>
        <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600' }}>
          {title}
        </Text>
        {subtitle ? (
          <Text
            variant="bodySmall"
            style={{ color: colors.onSurfaceVariant, marginTop: 2 }}
          >
            {subtitle}
          </Text>
        ) : null}
      </View>
      <Divider />
      <View style={[styles.body, { padding: spacing.md }]}>
        {hasResult ? (
          children
        ) : (
          <View style={[styles.empty, { paddingVertical: spacing.xl }]}>
            <MaterialCommunityIcons
              name={emptyIcon}
              size={48}
              color={colors.outlineVariant}
            />
            <Text
              variant="bodyMedium"
              style={{
                color: colors.onSurfaceVariant,
                marginTop: spacing.sm,
                textAlign: 'center',
              }}
            >
              {emptyText}
            </Text>
          </View>
        )}
      </View>
    </Surface>
  );
}

interface KeyValueRowProps {
  label: string;
  value: string;
  /** Optional accent color tone for the value. */
  tone?: 'default' | 'success' | 'error' | 'warning' | 'primary';
}

export function KeyValueRow({ label, value, tone = 'default' }: KeyValueRowProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  const valueColor =
    tone === 'success'
      ? colors.success
      : tone === 'error'
        ? colors.error
        : tone === 'warning'
          ? colors.warning
          : tone === 'primary'
            ? colors.primary
            : colors.onSurface;

  return (
    <View
      style={[
        styles.kvRow,
        {
          backgroundColor: colors.surfaceVariant,
          borderRadius: borderRadius.sm,
          paddingVertical: spacing.sm,
          paddingHorizontal: spacing.md,
        },
      ]}
    >
      <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, flex: 1 }}>
        {label}
      </Text>
      <Text
        variant="bodyMedium"
        style={{ color: valueColor, fontWeight: '600', fontVariant: ['tabular-nums'] }}
      >
        {value}
      </Text>
    </View>
  );
}

interface BigStatProps {
  label: string;
  value: string;
  background: string;
  foreground: string;
}

export function BigStat({ label, value, background, foreground }: BigStatProps) {
  const { spacing, borderRadius } = useAppTheme();
  return (
    <View
      style={[
        styles.bigStat,
        {
          backgroundColor: background,
          borderRadius: borderRadius.md,
          padding: spacing.md,
        },
      ]}
    >
      <Text variant="labelSmall" style={{ color: foreground, opacity: 0.85 }}>
        {label}
      </Text>
      <Text
        variant="titleLarge"
        style={{
          color: foreground,
          fontWeight: '700',
          marginTop: 2,
          fontVariant: ['tabular-nums'],
        }}
      >
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    overflow: 'hidden',
  },
  header: {},
  body: {},
  empty: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  kvRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  bigStat: {
    flex: 1,
    minWidth: '45%',
  },
});
