/**
 * Vault home — citizen Document Vault list with filters, tabs and quota bar.
 *
 * Stack route reachable from the dashboard QuickActions. Kept off the bottom
 * tab bar (already at 5 tabs — adding a 6th breaks the native Android pattern,
 * memory rule #15).
 */

import React, { useCallback, useMemo, useState } from 'react';
import {
  NativeScrollEvent,
  NativeSyntheticEvent,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { ActivityIndicator, Appbar, Divider, FAB, SegmentedButtons, Searchbar } from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useIsRestoring } from '@tanstack/react-query';

import { useAppTheme } from '@core/theme';
import { FullScreenSkeleton } from '@components/ui/skeleton';
import { AlertListItem } from '@modules/vault/components/alert-list-item';
import { DocumentEmptyState } from '@modules/vault/components/document-empty-state';
import {
  DocumentFilterChips,
  type VaultCategoryFilter,
  type VaultGenerationFilter,
} from '@modules/vault/components/document-filter-chips';
import { DocumentListItem } from '@modules/vault/components/document-list-item';
import { DocumentQuotaBar } from '@modules/vault/components/document-quota-bar';
import {
  useDismissAlert,
  useMarkAlertRead,
  useVaultAlerts,
  useVaultGenerated,
  useVaultList,
  useVaultStats,
  useVaultSearch,
} from '@modules/vault';
import type {
  AlertResponse,
  GeneratedDocumentResponse,
  UserDocumentListItem,
  VaultTabValue,
} from '@modules/vault';

// Maps the user-facing generation buckets to the backend `generation_type`
// values exposed by `GET /user-documents/generated`. (Backend enum:
// receipt, payment_receipt, certificate, attestation, summary,
// request_summary, confirmation.) The backend `?generation_type=` query
// accepts a single value, so we always fetch the full set and apply
// client-side multi-value filtering on the bucket below — keeps the chip
// "Recibos" inclusive of both `receipt` and `payment_receipt`, and
// "Resúmenes" inclusive of `summary` + `request_summary`.
const GENERATION_BUCKETS: Record<VaultGenerationFilter, string[]> = {
  all: [],
  receipts: ['receipt', 'payment_receipt'],
  certificates: ['certificate'],
  attestations: ['attestation'],
  summaries: ['summary', 'request_summary'],
  confirmations: ['confirmation'],
};

export default function VaultHomeScreen() {
  // Bottom safe-area inset — without it the FAB sits behind the Android nav
  // bar on most devices (see debug/tesoro/m1.jpg for the same bug on
  // /companies). Reused on the upload-tab FAB below.
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const isRestoring = useIsRestoring();
  const [tab, setTab] = useState<VaultTabValue>('uploads');
  const [categoryFilter, setCategoryFilter] = useState<VaultCategoryFilter>('all');
  const [generationFilter, setGenerationFilter] = useState<VaultGenerationFilter>('all');
  const [searchTerm, setSearchTerm] = useState('');

  const stats = useVaultStats();

  const listParams = useMemo(
    () => (categoryFilter === 'all' ? {} : { category: categoryFilter }),
    [categoryFilter],
  );
  const list = useVaultList(listParams);
  // Always fetch all generated docs — bucket filtering happens client-side
  // (see GENERATION_BUCKETS rationale above).
  const generated = useVaultGenerated();
  const generatedFilteredPages = useMemo(() => {
    const pages = generated.data?.pages ?? [];
    if (generationFilter === 'all') return pages;
    const allowed = new Set(GENERATION_BUCKETS[generationFilter]);
    return pages.map((p) => p.filter((d) => allowed.has(d.generation_type)));
  }, [generated.data, generationFilter]);
  const alerts = useVaultAlerts();
  const search = useVaultSearch(searchTerm);

  const markAlertRead = useMarkAlertRead();
  const dismissAlert = useDismissAlert();

  const handleItemPress = useCallback((item: UserDocumentListItem) => {
    router.push(`/documents/${item.id}` as never);
  }, []);

  const handleGeneratedPress = useCallback((item: GeneratedDocumentResponse) => {
    router.push(`/documents/${item.id}` as never);
  }, []);

  const handleAlertPress = useCallback(
    (alert: AlertResponse) => {
      if (!alert.is_read) {
        markAlertRead.mutate(alert.id);
      }
      const params = (alert as unknown as { action_params?: Record<string, string> }).action_params;
      const docId = params?.document_id;
      const workflow = params?.workflow_code;
      if (docId) {
        router.push(`/documents/${docId}` as never);
      } else if (workflow) {
        router.push(`/documents/readiness/${workflow}` as never);
      }
    },
    [markAlertRead],
  );

  const handleAlertLongPress = useCallback(
    (alert: AlertResponse) => dismissAlert.mutate(alert.id),
    [dismissAlert],
  );

  // ----- Render bodies per tab ---------------------------------------------
  // FINAL FIX (2026-05-02 — Option 2 after Option 1A failed on device).
  //
  // Bug history:
  //   The 3 lists used <FlatList style={flex:1}/> wrapped under a heavy
  //   ~270dp header stack (Appbar + QuotaBar + Tabs + Search + Chips). On
  //   Samsung Android devices, this combination produced a large empty gap
  //   between the chips row and the first visible item; users reported
  //   items "disappearing under a card" when scrolling up, which suggests
  //   the FlatList's virtualisation window was clipping items mid-render
  //   (post-fix captures: m1, m2, 2-5.jpg).
  //
  //   Option 1A (drop flexGrow:1, keep flex:1) was attempted in commit
  //   ab1d20a1 but did NOT fix the bug on real devices.
  //
  //   The /payments and /requests screens use the same FlatList pattern
  //   and do NOT bug — the difference is the much shorter pre-FlatList
  //   stack on those screens. The dashboard /(tabs)/index.tsx uses
  //   <View><RecentPaymentsList items.map()></View> (no FlatList) and
  //   never bugs.
  //
  // Final fix (Option 2):
  //   Replace FlatList with ScrollView + items.map(). No virtualisation,
  //   no flex/flexGrow stretching, no measurement quirks. The vault list
  //   is bounded by the user quota (≤100MB total → typically <200 docs),
  //   so the perf cost of rendering everything inline is negligible.
  //
  //   Pull-to-refresh: ScrollView's `refreshControl` prop, identical UX.
  //   Infinite scroll: onScroll handler triggers fetchNextPage near the
  //   bottom — same threshold as before (0.4 = 40% from end).
  //   Empty state: rendered inline when data.length === 0.
  const contentContainerStyle = useMemo(
    () => ({
      paddingTop: 8,
      paddingBottom: 96 + insets.bottom,
    }),
    [insets.bottom],
  );

  // Trigger fetchNextPage when the user has scrolled within 40% of the bottom.
  const handleScrollEndReached = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>, hasNextPage: boolean, isFetching: boolean, fetchNext: () => void) => {
      const { layoutMeasurement, contentOffset, contentSize } = e.nativeEvent;
      const distanceFromBottom = contentSize.height - (contentOffset.y + layoutMeasurement.height);
      // 40% of viewport height from the end (matches the previous
      // FlatList onEndReachedThreshold={0.4} behaviour).
      if (distanceFromBottom < layoutMeasurement.height * 0.4 && hasNextPage && !isFetching) {
        fetchNext();
      }
    },
    [],
  );

  const renderUploadsBody = () => {
    const showSearch = searchTerm.trim().length >= 2;
    const data = showSearch
      ? search.data ?? []
      : (list.data?.pages ?? []).flatMap((p) => p.items);
    const refreshing = list.isRefetching && !list.isFetchingNextPage;
    const isEmpty = data.length === 0;

    return (
      <ScrollView
        style={styles.flex1}
        contentContainerStyle={contentContainerStyle}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => list.refetch()}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
        onScroll={(e) =>
          handleScrollEndReached(
            e,
            !showSearch && (list.hasNextPage ?? false),
            list.isFetchingNextPage,
            () => list.fetchNextPage(),
          )
        }
        scrollEventThrottle={32}
      >
        {isEmpty ? (
          <DocumentEmptyState
            variant="uploads"
            onUpload={() => router.push('/documents/upload' as never)}
          />
        ) : (
          data.map((item, idx) => (
            <View key={item.id}>
              {idx > 0 ? <Divider /> : null}
              <DocumentListItem item={item} onPress={handleItemPress} />
            </View>
          ))
        )}
        {list.isFetchingNextPage ? (
          <ActivityIndicator style={{ paddingVertical: 16 }} color={colors.primary} />
        ) : null}
      </ScrollView>
    );
  };

  const renderGeneratedBody = () => {
    const data = generatedFilteredPages.flat();
    const isEmpty = data.length === 0;
    return (
      <ScrollView
        style={styles.flex1}
        contentContainerStyle={contentContainerStyle}
        refreshControl={
          <RefreshControl
            refreshing={generated.isRefetching}
            onRefresh={() => generated.refetch()}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
      >
        {isEmpty ? (
          <DocumentEmptyState variant="generated" />
        ) : (
          data.map((item, idx) => {
            // Adapt the GeneratedDocumentResponse shape to the generic
            // UserDocumentListItem the row renderer expects (see prior FlatList
            // implementation for rationale on category / expiry_status).
            const display: UserDocumentListItem = {
              id: item.id,
              document_type: item.generation_type,
              category: 'other',
              file_name: item.file_name,
              display_name: item.title,
              expiry_date: null,
              days_until_expiry: null,
              expiry_status: 'no_expiry',
              status: 'active',
              source: 'platform_generated',
              thumbnail_path: null,
              mime_type: 'application/pdf',
              file_size_bytes: 0,
              created_at: item.created_at,
              is_verified: true,
            };
            return (
              <View key={item.id}>
                {idx > 0 ? <Divider /> : null}
                <DocumentListItem
                  item={display}
                  onPress={() => handleGeneratedPress(item)}
                />
              </View>
            );
          })
        )}
      </ScrollView>
    );
  };

  const renderAlertsBody = () => {
    const data = alerts.data ?? [];
    const isEmpty = data.length === 0;
    return (
      <ScrollView
        style={styles.flex1}
        contentContainerStyle={contentContainerStyle}
        refreshControl={
          <RefreshControl
            refreshing={alerts.isRefetching}
            onRefresh={() => alerts.refetch()}
            colors={[colors.primary]}
            tintColor={colors.primary}
          />
        }
      >
        {isEmpty ? (
          <DocumentEmptyState variant="alerts" />
        ) : (
          data.map((item, idx) => (
            <View key={item.id}>
              {idx > 0 ? <Divider /> : null}
              <AlertListItem
                alert={item}
                onPress={handleAlertPress}
                onLongPress={handleAlertLongPress}
              />
            </View>
          ))
        )}
      </ScrollView>
    );
  };

  if (isRestoring) {
    return (
      <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
        <Stack.Screen options={{ headerShown: false }} />
        <Appbar.Header style={{ backgroundColor: colors.surface }}>
          <Appbar.BackAction onPress={() => router.back()} />
          <Appbar.Content title={t('vault.title')} />
        </Appbar.Header>
        <FullScreenSkeleton rows={8} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      {/* Phase 10/A — disable Material elevation on Paper header + searchbar.
          On Android these draw a 4dp/1dp drop-shadow that can visually clip
          the first scrollable items below them, producing the "items hidden
          under a card" effect reported on m1.jpg. payments/requests don't
          use these Paper components at all, which is why they don't bug. */}
      <Appbar.Header
        style={{ backgroundColor: colors.surface, elevation: 0, shadowOpacity: 0 }}
      >
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={t('vault.title')} />
      </Appbar.Header>

      {/* Single non-elevated header wrapper — mirrors the payments/requests
          pattern that doesn't bug. All sticky bits (quota, tabs, search,
          chips) live in this one container so the scrolling body sits
          flat below it without any shadow overlap. */}
      <View style={styles.headerWrapper}>
        {stats.data ? (
          <DocumentQuotaBar
            usedBytes={stats.data.quota_used_bytes}
            maxBytes={stats.data.quota_max_bytes}
          />
        ) : null}

        <View style={styles.tabsRow}>
          <SegmentedButtons
            value={tab}
            onValueChange={(v) => setTab(v as VaultTabValue)}
            buttons={[
              { value: 'uploads', label: t('vault.tabs.uploads') },
              { value: 'generated', label: t('vault.tabs.generated') },
              { value: 'alerts', label: t('vault.tabs.alerts') },
            ]}
          />
        </View>

        {tab === 'uploads' ? (
          <>
            <Searchbar
              placeholder={t('vault.search.placeholder')}
              value={searchTerm}
              onChangeText={setSearchTerm}
              style={styles.searchBar}
              elevation={0}
            />
            {searchTerm.trim().length < 2 ? (
              <DocumentFilterChips
                tab="uploads"
                value={categoryFilter}
                onChange={setCategoryFilter}
              />
            ) : null}
          </>
        ) : null}

        {tab === 'generated' ? (
          <DocumentFilterChips
            tab="generated"
            value={generationFilter}
            onChange={setGenerationFilter}
          />
        ) : null}
      </View>

      {tab === 'uploads' ? renderUploadsBody() : null}
      {tab === 'generated' ? renderGeneratedBody() : null}
      {tab === 'alerts' ? renderAlertsBody() : null}

      {tab === 'uploads' ? (
        <FAB
          icon="plus"
          style={[
            styles.fab,
            { backgroundColor: colors.primary, bottom: 16 + insets.bottom },
          ]}
          color="white"
          onPress={() => router.push('/documents/upload' as never)}
          accessibilityLabel={t('vault.upload.title')}
        />
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  // Phase 10/A — single non-elevated wrapper containing quota + tabs +
  // search + chips. Mirrors the payments/requests structure (one View
  // header, no Material elevation). Elevation 0 + shadowOpacity 0 are
  // applied per-component (Appbar.Header + Searchbar) above; the wrapper
  // itself just stacks them with no border or shadow.
  headerWrapper: {
    // No elevation, no border — purely a flex container.
  },
  // Used by each tab's body ScrollView so the FlatList → ScrollView
  // migration keeps the same height behaviour (fills residual vertical
  // space below the headerWrapper).
  flex1: { flex: 1 },
  tabsRow: { paddingHorizontal: 16, paddingVertical: 8 },
  searchBar: { marginHorizontal: 16, marginTop: 4, marginBottom: 4 },
  fab: {
    position: 'absolute',
    right: 16,
    // bottom is computed at render time from useSafeAreaInsets().
  },
});
