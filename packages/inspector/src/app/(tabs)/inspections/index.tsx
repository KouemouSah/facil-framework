/**
 * Inspections List Screen
 * Android native: flat list, 64dp items, dots + dividers, infinite scroll
 */

import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import { Divider, FAB, IconButton, Searchbar, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { router } from 'expo-router';

import { useAppTheme } from '@core/theme';
import { useDebounce } from '@core/hooks/use-debounce';
import { useInspectionList } from '@modules/inspections/services/inspections-hooks';
import { InspectionListItemRow } from '@modules/inspections/components/inspection-list-item';
import { InspectionFilters } from '@modules/inspections/components/inspection-filters';
import { EmptyState } from '@components/ui/empty-state';
import type { InspectionListItem, InspectionListFilters } from '@modules/inspections/types/inspection.types';

export default function InspectionsListScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  const [search, setSearch] = useState('');
  const debouncedSearch = useDebounce(search, 400);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Omit<InspectionListFilters, 'page'>>({
    sort_by: 'created_at',
    sort_dir: 'desc',
  });

  const queryFilters = useMemo(() => ({
    ...filters,
    ...(debouncedSearch.trim().length >= 2 ? { search: debouncedSearch.trim() } : {}),
  }), [filters, debouncedSearch]);

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    refetch,
    isRefetching,
  } = useInspectionList(queryFilters);

  const items = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  const total = data?.pages[0]?.total ?? 0;

  const renderItem = useCallback(
    ({ item }: { item: InspectionListItem }) => <InspectionListItemRow item={item} />,
    [],
  );

  const renderSeparator = useCallback(() => <Divider style={{ marginLeft: 38 }} />, []);

  const handleEndReached = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Text variant="headlineSmall" style={{ color: colors.primary, fontWeight: '700', flex: 1 }}>
            {t('inspection.list')}
          </Text>
          <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant }}>
            {total}
          </Text>
          <IconButton
            icon={showFilters ? 'filter-off' : 'filter-variant'}
            size={22}
            onPress={() => setShowFilters(!showFilters)}
            iconColor={colors.primary}
          />
        </View>
        <Searchbar
          value={search}
          onChangeText={setSearch}
          placeholder={t('search.placeholder')}
          style={styles.searchbar}
          inputStyle={styles.searchInput}
          elevation={0}
        />
      </View>

      {/* Filters */}
      {showFilters && (
        <InspectionFilters
          filters={filters}
          onApply={(f) => { setFilters(f); setShowFilters(false); }}
          onClear={() => { setFilters({ sort_by: 'created_at', sort_dir: 'desc' }); setShowFilters(false); }}
        />
      )}

      {/* List */}
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        ItemSeparatorComponent={renderSeparator}
        getItemLayout={(_, index) => ({ length: 65, offset: 65 * index, index })}
        onEndReached={handleEndReached}
        onEndReachedThreshold={0.3}
        refreshing={isRefetching}
        onRefresh={refetch}
        ListEmptyComponent={
          !isLoading ? (
            <EmptyState
              icon="clipboard-text-outline"
              title={t('common.noData')}
              description={t('search.noResults')}
            />
          ) : null
        }
        contentContainerStyle={items.length === 0 ? styles.emptyContainer : styles.listContent}
      />

      {/* FAB */}
      <FAB
        icon="plus"
        label={t('inspection.new')}
        onPress={() => router.push('/(tabs)/verify' as never)}
        style={[styles.fab, { bottom: insets.bottom + 16 }]}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', alignItems: 'center' },
  searchbar: { borderRadius: 8, height: 40, marginTop: 4 },
  searchInput: { fontSize: 14, minHeight: 40 },
  listContent: { paddingBottom: 80 },
  emptyContainer: { flexGrow: 1 },
  fab: { position: 'absolute', right: 16 },
});
