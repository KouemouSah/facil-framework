/**
 * Company Directory — Public search
 *
 * Search companies by name/NIF/activity.
 * List and Kanban view modes. Infinite scroll via useInfiniteQuery
 * + FlatList onEndReached.
 */

import { useState, useCallback, useRef, useMemo } from 'react';
import { StyleSheet, View, FlatList, Pressable, ActivityIndicator } from 'react-native';
import { Text, Searchbar, Divider, IconButton } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useIsRestoring } from '@tanstack/react-query';

import { useAppTheme } from '@core/theme';
import { AppMenuButton } from '@components/ui/app-menu';
import { SkeletonListItem, FullScreenSkeleton } from '@components/ui/skeleton';
import { useDirectorySearch } from '@modules/directory';
import type { DirectoryCompany } from '@modules/directory';

type ViewMode = 'list' | 'grid';

// ---------------------------------------------------------------------------
// Company Card (Grid/Kanban mode)
// ---------------------------------------------------------------------------

function CompanyCard({ item, colors }: { item: DirectoryCompany; colors: any }) {
  return (
    <View style={[s.card, { backgroundColor: colors.surface }]}>
      <View style={[s.cardIcon, { backgroundColor: colors.primaryContainer }]}>
        <MaterialCommunityIcons name="domain" size={22} color={colors.primary} />
      </View>
      <Text variant="titleSmall" style={{ fontWeight: '600', marginTop: 8 }} numberOfLines={2}>
        {item.legal_name}
      </Text>
      {item.nif && (
        <Text variant="labelSmall" style={{ color: colors.outline, marginTop: 2 }}>NIF: {item.nif}</Text>
      )}
      {item.city_name && (
        <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 4 }}>
          <MaterialCommunityIcons name="map-marker-outline" size={12} color={colors.outline} />
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, marginLeft: 4 }}>{item.city_name}</Text>
        </View>
      )}
      {item.sector_actividad && (
        <Text variant="labelSmall" style={{ color: colors.primary, marginTop: 4 }} numberOfLines={1}>
          {item.sector_actividad}
        </Text>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Company Row (List mode)
// ---------------------------------------------------------------------------

function CompanyRow({ item, colors }: { item: DirectoryCompany; colors: any }) {
  return (
    <View style={s.row}>
      <View style={[s.rowIcon, { backgroundColor: colors.primaryContainer }]}>
        <MaterialCommunityIcons name="domain" size={20} color={colors.primary} />
      </View>
      <View style={{ flex: 1, marginLeft: 12 }}>
        <Text variant="bodyMedium" style={{ fontWeight: '600' }} numberOfLines={1}>
          {item.legal_name}
        </Text>
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
          {item.nif && (
            <Text variant="labelSmall" style={{ color: colors.outline }}>NIF: {item.nif}</Text>
          )}
          {item.city_name && (
            <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>{item.city_name}</Text>
          )}
        </View>
        {item.objeto_social && (
          <Text variant="labelSmall" style={{ color: colors.outline, marginTop: 2 }} numberOfLines={1}>
            {item.objeto_social}
          </Text>
        )}
      </View>
      {item.zone_code && (
        <View style={[s.zonePill, { backgroundColor: colors.secondaryContainer }]}>
          <Text variant="labelSmall" style={{ color: colors.onSecondaryContainer, fontWeight: '600' }}>{item.zone_code}</Text>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function DirectorioScreen() {
  const router = useRouter();
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const isRestoring = useIsRestoring();

  const [query, setQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [searchParams, setSearchParams] = useState<Record<string, string>>({ page_size: '20' });
  const debounceRef = useRef<NodeJS.Timeout>(null);

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
  } = useDirectorySearch(searchParams, true);

  const handleSearch = useCallback((text: string) => {
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchParams((prev) => {
        const next: Record<string, string> = { ...prev };
        if (text.trim()) next.q = text.trim();
        else delete next.q;
        return next;
      });
    }, 350);
  }, []);

  const companies = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data?.pages],
  );

  const total = data?.pages[0]?.total ?? 0;

  const handleEndReached = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  if (isRestoring) {
    return (
      <SafeAreaView style={[s.container, { backgroundColor: '#F5F5F5' }]}>
        <FullScreenSkeleton rows={8} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[s.container, { backgroundColor: '#F5F5F5' }]}>
      {/* Header */}
      <View style={[s.header, { backgroundColor: colors.surface }]}>
        <Pressable onPress={() => router.back()} style={{ padding: 4 }}>
          <MaterialCommunityIcons name="arrow-left" size={24} color={colors.onSurface} />
        </Pressable>
        <Text variant="titleMedium" style={{ fontWeight: '600', marginLeft: 12, flex: 1 }}>
          {t('directory.title')}
        </Text>
        {/* View mode toggle */}
        <IconButton
          icon={viewMode === 'list' ? 'view-grid-outline' : 'view-list-outline'}
          size={22}
          onPress={() => setViewMode((v) => (v === 'list' ? 'grid' : 'list'))}
          iconColor={colors.primary}
        />
        <AppMenuButton />
      </View>

      {/* Search bar — rounded, grey background */}
      <View style={{ paddingHorizontal: 16, paddingVertical: 10, backgroundColor: colors.surface }}>
        <Searchbar
          value={query}
          onChangeText={handleSearch}
          placeholder={t('directory.searchPlaceholder')}
          style={[s.searchBar, { backgroundColor: '#EEEEEE' }]}
          inputStyle={{ fontSize: 14 }}
        />
      </View>

      {/* Results count */}
      {data && (
        <View style={{ paddingHorizontal: 16, paddingVertical: 8 }}>
          <Text variant="labelSmall" style={{ color: colors.outline }}>
            {companies.length} / {total} {t('directory.results')}
          </Text>
        </View>
      )}

      {/* List */}
      {isLoading ? (
        <View>
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonListItem key={`sk-${i}`} />
          ))}
        </View>
      ) : (
        <FlatList
          key={viewMode}
          data={companies}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) =>
            viewMode === 'list'
              ? <CompanyRow item={item} colors={colors} />
              : <CompanyCard item={item} colors={colors} />
          }
          {...(viewMode === 'grid' ? {
            numColumns: 2,
            columnWrapperStyle: { paddingHorizontal: 12, gap: 10, marginBottom: 10 },
          } : {})}
          ItemSeparatorComponent={viewMode === 'list' ? () => <Divider style={{ marginLeft: 60 }} /> : undefined}
          contentContainerStyle={{ paddingTop: viewMode === 'grid' ? 4 : 0, paddingBottom: 24 }}
          onEndReached={handleEndReached}
          onEndReachedThreshold={0.5}
          ListFooterComponent={
            isFetchingNextPage ? (
              <View style={s.footer}>
                <ActivityIndicator size="small" color={colors.primary} />
              </View>
            ) : null
          }
          ListEmptyComponent={
            <View style={{ padding: 32, alignItems: 'center' }}>
              <MaterialCommunityIcons name="office-building-outline" size={48} color={colors.outline} />
              <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginTop: 12 }}>
                {t('directory.noResults')}
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10 },
  searchBar: { borderRadius: 24, elevation: 0 },
  // List mode
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14 },
  rowIcon: { width: 40, height: 40, borderRadius: 20, justifyContent: 'center', alignItems: 'center' },
  zonePill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  // Grid/Kanban mode
  card: { flex: 1, borderRadius: 12, padding: 14, elevation: 1 },
  cardIcon: { width: 40, height: 40, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  // Footer loader
  footer: { paddingVertical: 16, alignItems: 'center' },
});
