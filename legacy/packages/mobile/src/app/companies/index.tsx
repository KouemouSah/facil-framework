/**
 * Companies list — "Mis Empresas" stack screen.
 * Reachable from the dashboard QuickAction.
 */

import React, { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet } from 'react-native';
import { Appbar, Divider, FAB } from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useIsRestoring } from '@tanstack/react-query';

import { useAppTheme } from '@core/theme';
import { FullScreenSkeleton } from '@components/ui/skeleton';
import { CompanyEmptyState } from '@modules/companies/components/company-empty-state';
import {
  BundleCompanyCard,
  useBundleMyCompanies,
  type MyCompanyStatusItem,
} from '@modules/bundles';

export default function CompaniesIndexScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  // Bottom inset accounts for the Android system nav bar — without it the FAB
  // sits 24dp above the screen edge but BEHIND the gesture/3-button bar on
  // most devices (see debug/tesoro/m1.jpg).
  const insets = useSafeAreaInsets();
  const isRestoring = useIsRestoring();
  const list = useBundleMyCompanies();

  const data = list.data?.companies ?? [];
  const refreshing = list.isRefetching;

  const handleItemPress = useCallback((item: MyCompanyStatusItem) => {
    router.push(`/companies/${item.company.id}` as never);
  }, []);

  // Pre-select the company in the bundle wizard so the user lands directly
  // on the obligations screen (consumed by useBundleWizard via
  // useLocalSearchParams.company_id).
  const handlePay = useCallback((item: MyCompanyStatusItem) => {
    router.push(
      `/bundle-wizard?company_id=${encodeURIComponent(item.company.id)}` as never,
    );
  }, []);

  // FAB → padron upload flow (bundle-wizard skip-to-upload via `mode=new`).
  // Mirrors web /dashboard/empresas → /dashboard/bundle-payment?mode=new
  // which calls wizard.requestNewCompany() to land directly on the
  // DOCUMENT_UPLOAD step instead of the company-identification picker
  // (B5a parity, m13.jpg).
  const handleCreate = useCallback(() => {
    router.push('/bundle-wizard?mode=new' as never);
  }, []);

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={t('companies.title')} />
      </Appbar.Header>

      {isRestoring || list.isLoading ? (
        <FullScreenSkeleton rows={8} />
      ) : (
        <FlatList
          data={data}
          keyExtractor={(item) => item.company.id}
          renderItem={({ item }) => (
            <BundleCompanyCard item={item} onPress={handleItemPress} onPay={handlePay} />
          )}
          ItemSeparatorComponent={() => <Divider />}
          ListEmptyComponent={<CompanyEmptyState onCreate={handleCreate} />}
          contentContainerStyle={data.length === 0 ? styles.emptyContent : undefined}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => list.refetch()}
              colors={[colors.primary]}
              tintColor={colors.primary}
            />
          }
          initialNumToRender={10}
          maxToRenderPerBatch={15}
          windowSize={10}
          removeClippedSubviews
        />
      )}

      <FAB
        icon="plus"
        style={[
          styles.fab,
          { backgroundColor: colors.primary, bottom: 16 + insets.bottom },
        ]}
        color="white"
        onPress={handleCreate}
        accessibilityLabel={t('companies.create.title')}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyContent: { flexGrow: 1, justifyContent: 'center' },
  fab: {
    position: 'absolute',
    right: 16,
    // bottom is computed at render time from useSafeAreaInsets() — see usage.
  },
});
