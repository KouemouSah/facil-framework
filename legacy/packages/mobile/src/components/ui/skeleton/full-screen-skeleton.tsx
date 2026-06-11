/**
 * FullScreenSkeleton — placeholder shown while `useIsRestoring()` is true,
 * i.e. while React Query is rehydrating its persisted cache from MMKV.
 *
 * Even though MMKV reads are sync (~5-50ms), `<PersistQueryClientProvider>`
 * still flips `isRestoring` to `true` for one render cycle on cold start.
 * Without this gate, the screens that mount during that cycle see queries
 * in `pending` state and show their own loading UI — sometimes triggering
 * a redundant network refetch even when valid cached data exists.
 *
 * Use this component on entry-point screens where the user feels the
 * "long load" most acutely:
 *   - dashboard tab home
 *   - services / directory / companies catalog screens
 *   - documents vault home
 */

import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Divider } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import { SkeletonListItem } from './skeleton-list-item';

interface FullScreenSkeletonProps {
  /**
   * Number of skeleton rows to render (matches the typical FlatList density).
   * Default: 8 — covers ~512dp of vertical space on most phones.
   */
  rows?: number;
  /**
   * If true, renders a centered ActivityIndicator instead of skeleton rows.
   * Use sparingly — skeletons feel faster than spinners.
   */
  spinner?: boolean;
}

export function FullScreenSkeleton({ rows = 8, spinner = false }: FullScreenSkeletonProps) {
  const { colors } = useAppTheme();

  if (spinner) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.primary} />
      </View>
    );
  }

  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[styles.list, { backgroundColor: colors.background }]}
    >
      {Array.from({ length: rows }).map((_, i) => (
        <View key={`skel-${i}`}>
          <SkeletonListItem />
          {i < rows - 1 ? <Divider /> : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  list: { flex: 1 },
});
