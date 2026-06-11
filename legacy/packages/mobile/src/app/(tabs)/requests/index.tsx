/**
 * Requests List Screen
 *
 * Displays the user's service requests with:
 * - Debounced search bar
 * - Horizontal chip filters for status
 * - Infinite-scroll FlatList with pull-to-refresh
 * - Empty state with CTA to create a new request
 * - FAB "Nueva Solicitud" to navigate to the services catalog
 */

import { useState, useRef, useCallback, useMemo } from 'react';
import { StyleSheet, View, FlatList , ScrollView } from 'react-native';
import { Text, Searchbar, Chip, FAB, ActivityIndicator, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { EmptyState } from '@components/ui/empty-state';
import { SkeletonListItem } from '@components/ui/skeleton';
import { useRequests } from '@modules/service-requests';
import type { ServiceRequestListItem } from '@modules/service-requests';
import { RequestListItem } from '@modules/service-requests/components/request-list-item';

// ---------------------------------------------------------------------------
// Status filter config
// ---------------------------------------------------------------------------

const STATUS_FILTERS = [
  'all',
  'submitted',
  'processing',
  'under_review',
  'completed',
  'rejected',
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number];

/** Matches RequestListItem layout (12dp pad + 2 lines + 12dp pad + Divider 1px). */
const ROW_HEIGHT = 65;

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

function RequestsListContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  // --- State ---------------------------------------------------------------
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<StatusFilter>('all');

  // --- Debounced search (300 ms) -------------------------------------------
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearchChange = useCallback((text: string) => {
    setSearchQuery(text);
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedSearch(text.trim());
    }, 300);
  }, []);

  // --- Query ---------------------------------------------------------------
  const filters = useMemo(
    () => ({
      status: selectedStatus === 'all' ? undefined : selectedStatus,
      search: debouncedSearch || undefined,
      page_size: 10,
    }),
    [selectedStatus, debouncedSearch],
  );

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isRefetching,
    refetch,
    error,
  } = useRequests(filters);

  // Flatten pages into a single list
  const requests: ServiceRequestListItem[] = useMemo(
    () => data?.pages.flatMap((page) => page.requests) ?? [],
    [data],
  );

  // --- Handlers ------------------------------------------------------------

  const handleLoadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  const handlePressRequest = useCallback(
    (id: string) => {
      router.push(`/(tabs)/requests/${id}`);
    },
    [router],
  );

  const getStatusLabel = (status: StatusFilter): string => {
    if (status === 'all') return t('common.seeAll');
    return t(`requests.status.${status}`);
  };

  // --- Render helpers ------------------------------------------------------

  const renderItem = useCallback(
    ({ item }: { item: ServiceRequestListItem }) => (
      <RequestListItem item={item} onPress={() => handlePressRequest(item.id)} />
    ),
    [handlePressRequest],
  );

  const keyExtractor = useCallback(
    (item: ServiceRequestListItem) => item.id,
    [],
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
        icon="file-document-outline"
        title={t('dashboard.noRequests')}
        description={t('dashboard.startFirstRequest')}
        actionLabel={t('requests.new')}
        onAction={() => router.push('/wizard/select-workflow' as never)}
      />
    );
  }, [isLoading, error, colors.primary, t, router, refetch]);

  // --- Render --------------------------------------------------------------

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      {/* Header */}
      <View style={[styles.header, { padding: spacing.md }]}>
        <Text
          variant="headlineSmall"
          style={[styles.title, { color: colors.onBackground, marginBottom: spacing.md }]}
        >
          {t('requests.title')}
        </Text>

        {/* Search bar */}
        <Searchbar
          placeholder={t('common.search')}
          onChangeText={handleSearchChange}
          value={searchQuery}
          style={[
            styles.searchBar,
            {
              backgroundColor: colors.surfaceVariant,
              borderRadius: borderRadius.md,
              marginBottom: spacing.sm,
            },
          ]}
          inputStyle={{ color: colors.onSurface }}
          iconColor={colors.onSurfaceVariant}
          placeholderTextColor={colors.outline}
        />

        {/* Status filter chips */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={[styles.chipRow, { gap: spacing.xs }]}
        >
          {STATUS_FILTERS.map((status) => (
            <Chip
              key={status}
              selected={selectedStatus === status}
              onPress={() => setSelectedStatus(status)}
              mode={selectedStatus === status ? 'flat' : 'outlined'}
              style={
                selectedStatus === status
                  ? { backgroundColor: colors.primaryContainer }
                  : undefined
              }
              textStyle={
                selectedStatus === status
                  ? { color: colors.onPrimaryContainer }
                  : { color: colors.onSurfaceVariant }
              }
              compact
            >
              {getStatusLabel(status)}
            </Chip>
          ))}
        </ScrollView>
      </View>

      {/* Request list */}
      <FlatList
        data={requests}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        ItemSeparatorComponent={Divider}
        contentContainerStyle={[
          styles.listContent,
          requests.length === 0 && styles.listEmpty,
          { paddingTop: spacing.sm, paddingBottom: 80 },
        ]}
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        refreshing={isRefetching}
        onRefresh={handleRefresh}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmpty}
        showsVerticalScrollIndicator={false}
        // P8.3 — perf knobs (RequestListItem is 64dp tall, padding+2 lines).
        getItemLayout={(_, index) => ({
          length: ROW_HEIGHT,
          offset: ROW_HEIGHT * index,
          index,
        })}
        initialNumToRender={15}
        maxToRenderPerBatch={20}
        windowSize={10}
        removeClippedSubviews
      />

      {/* FAB */}
      <FAB
        icon="plus"
        label={t('requests.new')}
        onPress={() => router.push('/wizard/select-workflow' as never)}
        style={[
          styles.fab,
          { backgroundColor: colors.primary, borderRadius: borderRadius.xl },
        ]}
        color={colors.onPrimary}
      />
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {},
  title: {
    fontWeight: '700',
  },
  searchBar: {
    elevation: 0,
  },
  chipRow: {
    flexDirection: 'row',
    paddingVertical: 4,
  },
  listContent: {
    flexGrow: 1,
  },
  listEmpty: {
    flex: 1,
  },
  footer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  fab: {
    position: 'absolute',
    bottom: 16,
    right: 16,
  },
});

export default function RequestsListScreen() {
  return (
    <AuthGuard>
      <RequestsListContent />
    </AuthGuard>
  );
}
