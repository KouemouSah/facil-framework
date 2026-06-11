/**
 * Support Tickets — list of the current user's tickets.
 * Connected to `GET /support/tickets/my` (P6.3).
 */

import { useCallback, useMemo, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Chip,
  Divider,
  FAB,
  IconButton,
  Text,
} from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { EmptyState } from '@components/ui/empty-state';
import { SkeletonListItem } from '@components/ui/skeleton';
import {
  TicketListItem,
  useMyTickets,
  type SupportTicket,
  type TicketStatus,
} from '@modules/support';

const FILTERS = ['all', 'open', 'resolved', 'closed'] as const;
type Filter = (typeof FILTERS)[number];

const ITEM_HEIGHT = 64;

function SupportListContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  // Bottom safe-area inset — without it the FAB sits behind the Android nav
  // gesture bar on most devices (see debug/tesoro/m12.jpg). Same pattern as
  // documents/index.tsx:65,316.
  const insets = useSafeAreaInsets();
  const [filter, setFilter] = useState<Filter>('all');

  const status: TicketStatus | undefined = filter === 'all' ? undefined : filter;

  const {
    data,
    isLoading,
    isRefetching,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    error,
  } = useMyTickets({ status, page_size: 20 });

  const tickets: SupportTicket[] = useMemo(
    () => data?.pages.flatMap((page) => page.tickets) ?? [],
    [data],
  );

  const handlePress = useCallback(
    (id: number) => {
      router.push(`/support/${id}` as never);
    },
    [router],
  );

  const handleLoadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const renderItem = useCallback(
    ({ item }: { item: SupportTicket }) => (
      <TicketListItem item={item} onPress={handlePress} />
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
        icon="headset"
        title={t('support.list.empty')}
        description={t('support.title')}
        actionLabel={t('support.newTicket')}
        onAction={() => router.push('/support/new' as never)}
      />
    );
  }, [isLoading, error, colors.primary, refetch, router, t]);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[
          styles.topBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
        ]}
      >
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {t('support.list.title')}
        </Text>
      </View>

      <View style={[styles.filterBar, { paddingHorizontal: spacing.md }]}>
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
              {t(`support.list.filter.${f}`, { defaultValue: f })}
            </Chip>
          ))}
        </ScrollView>
      </View>

      <FlatList
        data={tickets}
        renderItem={renderItem}
        keyExtractor={(item) => String(item.id)}
        ItemSeparatorComponent={Divider}
        contentContainerStyle={[
          styles.listContent,
          tickets.length === 0 && styles.listEmpty,
          { paddingTop: spacing.sm, paddingBottom: 96 },
        ]}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        refreshing={isRefetching}
        onRefresh={refetch}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmpty}
        showsVerticalScrollIndicator={false}
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

      <FAB
        icon="plus"
        label={t('support.newTicket')}
        onPress={() => router.push('/support/new' as never)}
        style={[
          styles.fab,
          {
            backgroundColor: colors.primary,
            borderRadius: borderRadius.xl,
            bottom: 16 + insets.bottom,
          },
        ]}
        color={colors.onPrimary}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  filterBar: { paddingVertical: 8 },
  chipRow: { flexDirection: 'row', paddingVertical: 4 },
  listContent: { flexGrow: 1 },
  listEmpty: { flex: 1 },
  footer: { paddingVertical: 16, alignItems: 'center' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  // bottom is computed at render time from useSafeAreaInsets() — see B3 fix.
  fab: { position: 'absolute', right: 16 },
});

export default function SupportListScreen() {
  return (
    <AuthGuard>
      <SupportListContent />
    </AuthGuard>
  );
}
