/**
 * Skeleton loading placeholders — Android native shimmer effect
 * Replaces spinner loading screens with content-shaped placeholders.
 */

import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { useAppTheme } from '@core/theme';

interface SkeletonProps {
  width?: number | string;
  height?: number;
  borderRadius?: number;
  style?: object;
}

export function Skeleton({ width = '100%', height = 16, borderRadius = 4, style }: SkeletonProps) {
  const { colors } = useAppTheme();
  const opacity = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.7, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.3, duration: 800, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [opacity]);

  return (
    <Animated.View
      style={[
        { width: width as number, height, borderRadius, backgroundColor: colors.surfaceVariant, opacity },
        style,
      ]}
    />
  );
}

/** Skeleton for a list item row (64dp) */
export function SkeletonListItem() {
  return (
    <View style={skStyles.listItem}>
      <Skeleton width={10} height={10} borderRadius={5} />
      <View style={skStyles.listBody}>
        <Skeleton width="70%" height={14} />
        <Skeleton width="45%" height={10} style={{ marginTop: 6 }} />
      </View>
      <Skeleton width={50} height={12} />
    </View>
  );
}

/** Skeleton for stats grid (4 KPIs) */
export function SkeletonStatsGrid() {
  return (
    <View style={skStyles.statsGrid}>
      {[1, 2, 3, 4].map((i) => (
        <View key={i} style={skStyles.statItem}>
          <Skeleton width={48} height={32} borderRadius={4} />
          <Skeleton width={40} height={10} borderRadius={2} style={{ marginTop: 6 }} />
        </View>
      ))}
    </View>
  );
}

/** Skeleton for dashboard screen */
export function SkeletonDashboard() {
  return (
    <View style={skStyles.dashboard}>
      <Skeleton width="50%" height={20} style={{ marginBottom: 8 }} />
      <Skeleton width="70%" height={14} style={{ marginBottom: 20 }} />
      <SkeletonStatsGrid />
      <View style={{ marginTop: 20, gap: 4 }}>
        <SkeletonListItem />
        <SkeletonListItem />
        <SkeletonListItem />
      </View>
    </View>
  );
}

/** Skeleton for inspection detail */
export function SkeletonInspectionDetail() {
  return (
    <View style={skStyles.dashboard}>
      <Skeleton width="60%" height={18} style={{ marginBottom: 6 }} />
      <Skeleton width="80%" height={12} style={{ marginBottom: 20 }} />
      <Skeleton width="100%" height={44} borderRadius={8} style={{ marginBottom: 12 }} />
      <Skeleton width="100%" height={96} borderRadius={8} style={{ marginBottom: 12 }} />
      <Skeleton width="100%" height={32} borderRadius={8} style={{ marginBottom: 12 }} />
      <Skeleton width="100%" height={64} borderRadius={8} />
    </View>
  );
}

const skStyles = StyleSheet.create({
  listItem: { flexDirection: 'row', alignItems: 'center', height: 64, paddingHorizontal: 16, gap: 12 },
  listBody: { flex: 1 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12 },
  statItem: { width: '50%', alignItems: 'center', paddingVertical: 12 },
  dashboard: { padding: 16 },
});
