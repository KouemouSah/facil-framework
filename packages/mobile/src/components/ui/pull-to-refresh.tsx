/**
 * Pull-to-refresh wrapper
 *
 * Wraps children in a ScrollView with a themed RefreshControl.
 * The `onRefresh` callback should return a Promise; the spinner
 * dismisses automatically when the promise settles.
 */

import { useState, useCallback } from 'react';
import { ScrollView, RefreshControl, type ScrollViewProps, StyleSheet } from 'react-native';

import { useAppTheme } from '@core/theme';

interface PullToRefreshProps {
  /** Async callback invoked when the user pulls to refresh. */
  onRefresh: () => Promise<void>;
  children: React.ReactNode;
  /** Additional ScrollView props forwarded to the inner ScrollView. */
  scrollViewProps?: Omit<ScrollViewProps, 'refreshControl'>;
}

export function PullToRefresh({ onRefresh, children, scrollViewProps }: PullToRefreshProps) {
  const { colors } = useAppTheme();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }, [onRefresh]);

  return (
    <ScrollView
      contentContainerStyle={styles.content}
      {...scrollViewProps}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          colors={[colors.primary]}
          tintColor={colors.primary}
          progressBackgroundColor={colors.surface}
        />
      }
    >
      {children}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
  },
});
