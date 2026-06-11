/**
 * Payments History Screen — paginated infinite list of the user's payments.
 *
 * Reached from the profile entry "Mes paiements" or after a successful
 * wizard payment-result. Filter chips: All / Pending / Completed / Failed.
 */

import { useCallback, useMemo, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Chip, Divider, Text } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { EmptyState } from '@components/ui/empty-state';
import { SkeletonListItem } from '@components/ui/skeleton';
import {
  PaymentListItem,
  usePaymentsList,
  type Payment,
  type PaymentStatus,
} from '@modules/payments';

const FILTERS = ['all', 'pending', 'completed', 'failed'] as const;
type Filter = (typeof FILTERS)[number];

// Matches PaymentListItem layout: 12 (top pad) + ~38 (two lines) + 12 (bot pad)
// + 1 (Divider). Keep in sync with payment-list-item.tsx and the divider.
const ITEM_HEIGHT = 63;

function PaymentsListContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();
  const [filter, setFilter] = useState<Filter>('all');

  const status: PaymentStatus | undefined = filter === 'all' ? undefined : filter;

  const {
    data,
    isLoading,
    isRefetching,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    error,
  } = usePaymentsList({ status, page_size: 20 });

  const payments: Payment[] = useMemo(
    () => data?.pages.flatMap((page) => page.payments) ?? [],
    [data],
  );

  const handleLoadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const handlePress = useCallback(
    (id: string) => {
      router.push(`/(tabs)/payments/${id}` as never);
    },
    [router],
  );

  const renderItem = useCallback(
    ({ item }: { item: Payment }) => (
      <PaymentListItem item={item} onPress={handlePress} />
    ),
    [handlePress],
  );

  const renderFooter = useCallback(() => {
    if (!isFetchingNextPage) return null;
    return (
      <View style={styles.footer}>
        <ActivityIndicator size="small" color={colors.primary} />
      </View>
    );
  }, [isFetchingNextPage, colors.primary]);

  const renderEmpty = useCallback(() => {
    if (isLoading) {
      return (
        <View>
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonListItem key={`sk-${i}`} />
          ))}
        </View>
      );
    }
    if (error) {
      const message = error instanceof Error ? error.message : t('errors.serverError');
      return (
        <EmptyState
          icon="alert-circle-outline"
          title={t('common.error')}
          description={message}
          actionLabel={t('common.retry')}
          onAction={() => refetch()}
        />
      );
    }
    return (
      <EmptyState
        icon="cash-multiple"
        title={t('payments.list.empty')}
        description={t('dashboard.startFirstRequest')}
      />
    );
  }, [isLoading, error, colors.primary, refetch, t]);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View style={[styles.header, { padding: spacing.md }]}>
        <Text
          variant="headlineSmall"
          style={[styles.title, { color: colors.onBackground, marginBottom: spacing.md }]}
        >
          {t('payments.list.title')}
        </Text>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={[styles.chipRow, { gap: spacing.xs }]}
        >
          {FILTERS.map((f) => (
            <Chip
              key={f}
              selected={filter === f}
              onPress={() => setFilter(f)}
              mode={filter === f ? 'flat' : 'outlined'}
              style={
                filter === f ? { backgroundColor: colors.primaryContainer } : undefined
              }
              textStyle={
                filter === f
                  ? { color: colors.onPrimaryContainer }
                  : { color: colors.onSurfaceVariant }
              }
              compact
            >
              {t(`payments.list.filter.${f}`)}
            </Chip>
          ))}
        </ScrollView>
      </View>

      <FlatList
        data={payments}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        ItemSeparatorComponent={Divider}
        contentContainerStyle={[
          styles.listContent,
          payments.length === 0 && styles.listEmpty,
          { paddingTop: spacing.sm, paddingBottom: 24 },
        ]}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        refreshing={isRefetching}
        onRefresh={refetch}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmpty}
        showsVerticalScrollIndicator={false}
        // Perf — payment items have a fixed height (12 + 2-line content + 12).
        // Pinning getItemLayout lets RN skip layout passes during scroll.
        getItemLayout={(_, index) => ({
          length: ITEM_HEIGHT,
          offset: ITEM_HEIGHT * index,
          index,
        })}
        initialNumToRender={15}
        maxToRenderPerBatch={20}
        windowSize={10}
        removeClippedSubviews
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: {},
  title: { fontWeight: '700' },
  chipRow: { flexDirection: 'row', paddingVertical: 4 },
  listContent: { flexGrow: 1 },
  listEmpty: { flex: 1 },
  footer: { paddingVertical: 16, alignItems: 'center' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
});

export default function PaymentsListScreen() {
  return (
    <AuthGuard>
      <PaymentsListContent />
    </AuthGuard>
  );
}
