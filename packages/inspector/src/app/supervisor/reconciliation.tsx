/**
 * Cash Reconciliation Screen — Validate field cash collections
 * Supervisor double-validates payments collected by agents in the field.
 */

import React, { useCallback } from 'react';
import { Alert, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Button, Divider, Snackbar, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { formatCurrency, formatDate } from '@core/utils/format';
import { extractApiError } from '@core/api/errors';
import { EmptyState } from '@components/ui/empty-state';
import { LoadingScreen } from '@components/ui/loading-screen';
import {
  useSupervisorReconciliation,
  useValidateReconciliation,
} from '@modules/inspections/services/inspections-hooks';
import type { ReconciliationItem } from '@modules/inspections/services/inspections-api';

export default function ReconciliationScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { agentContext } = useAuth();
  const insets = useSafeAreaInsets();

  const { data, isLoading, refetch, isRefetching } = useSupervisorReconciliation();
  const validateMutation = useValidateReconciliation();
  const [snack, setSnack] = React.useState('');
  const [error, setError] = React.useState('');

  const items = data?.items ?? [];
  const totalAmount = data?.total_amount ?? 0;
  const totalCount = data?.total_count ?? 0;

  const handleValidate = useCallback(
    (item: ReconciliationItem) => {
      Alert.alert(
        t('supervisor.validate'),
        `${item.company_name ?? '—'}\n${formatCurrency(item.payment_amount ?? 0)}`,
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('supervisor.validate'),
            onPress: async () => {
              try {
                setError('');
                const result = await validateMutation.mutateAsync(item.id);
                setSnack(
                  `${t('supervisor.validate')}: ${result.routed_obligations} obligations`,
                );
              } catch (err) {
                setError(extractApiError(err).message);
              }
            },
          },
        ],
      );
    },
    [validateMutation, t],
  );

  const renderItem = useCallback(
    ({ item }: { item: ReconciliationItem }) => (
      <View style={styles.item}>
        <View style={styles.itemBody}>
          <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }} numberOfLines={1}>
            {item.company_name ?? '—'}
          </Text>
          <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
            {item.company_nif ?? ''} {item.inspection_date ? `• ${formatDate(item.inspection_date)}` : ''}
          </Text>
          <View style={styles.amountRow}>
            <MaterialCommunityIcons name="cash" size={16} color={colors.primary} />
            <Text variant="titleSmall" style={{ color: colors.primary, fontWeight: '700', marginLeft: 4 }}>
              {formatCurrency(item.payment_amount ?? 0)}
            </Text>
          </View>
          {item.payment_receipt_number && (
            <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
              {item.payment_receipt_number}
            </Text>
          )}
        </View>
        <Button
          mode="contained"
          icon="check"
          onPress={() => handleValidate(item)}
          loading={validateMutation.isPending}
          disabled={validateMutation.isPending}
          compact
          style={styles.validateButton}
        >
          {t('supervisor.validate')}
        </Button>
      </View>
    ),
    [colors, handleValidate, validateMutation.isPending, t],
  );

  if (isLoading) return <LoadingScreen />;

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 4 }]}>
        <View style={styles.headerRow}>
          <Button icon="arrow-left" onPress={() => router.back()} textColor={colors.primary} compact>
            {t('inspection.back')}
          </Button>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('supervisor.reconciliation')}
          </Text>
          <View style={{ width: 60 }} />
        </View>
      </View>

      {/* Summary banner */}
      {totalCount > 0 && (
        <View style={[styles.banner, { backgroundColor: colors.surfaceVariant }]}>
          <MaterialCommunityIcons name="cash-fast" size={20} color={colors.primary} />
          <Text variant="bodyMedium" style={{ color: colors.onSurface, marginLeft: 8 }}>
            {totalCount} {t('supervisor.reconciliation').toLowerCase()}
          </Text>
          <Text variant="titleSmall" style={{ color: colors.primary, fontWeight: '700', marginLeft: 'auto' }}>
            {formatCurrency(totalAmount)}
          </Text>
        </View>
      )}

      {/* Scope badge */}
      {agentContext && (
        <View style={styles.scopeInfo}>
          <MaterialCommunityIcons name="map-marker-outline" size={14} color={colors.onSurfaceVariant} />
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, marginLeft: 4 }}>
            {agentContext.isMainOffice
              ? t('dashboard.allLocations', { defaultValue: 'All locations' })
              : `${agentContext.locationCity} (${agentContext.locationRegion})`}
          </Text>
        </View>
      )}

      {error ? (
        <Text variant="bodySmall" style={{ color: colors.error, paddingHorizontal: 16, paddingVertical: 4 }}>
          {error}
        </Text>
      ) : null}

      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        ItemSeparatorComponent={() => <Divider style={{ marginLeft: 16 }} />}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={refetch} colors={[colors.primary]} />
        }
        ListEmptyComponent={
          <EmptyState
            icon="check-circle-outline"
            title={t('common.noData')}
            description={t('supervisor.allReconciled', { defaultValue: 'All field collections reconciled' })}
          />
        }
        contentContainerStyle={items.length === 0 ? styles.emptyContainer : styles.listContent}
      />

      <Snackbar
        visible={!!snack}
        onDismiss={() => setSnack('')}
        duration={3000}
        action={{ label: 'OK', onPress: () => setSnack('') }}
      >
        {snack}
      </Snackbar>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 8, paddingBottom: 4 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  banner: { flexDirection: 'row', alignItems: 'center', marginHorizontal: 16, marginBottom: 8, padding: 12, borderRadius: 8 },
  scopeInfo: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, marginBottom: 8 },
  listContent: { paddingBottom: 32 },
  emptyContainer: { flexGrow: 1 },
  item: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: 16 },
  itemBody: { flex: 1, gap: 2 },
  amountRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  validateButton: { borderRadius: 8, marginLeft: 12 },
});
