/**
 * Company payment history (citizen view) — full-screen route reachable from
 * the kebab menu of /companies/[id]. Wired on
 *   GET /bundle-workflow/my-companies/{id}/payments
 *
 * Promoted out of the inline Card on the detail screen (B5b 2026-04-29) so
 * the detail screen breathes (deadline / total / paid chips + license CTA at
 * a glance), and so payment listing has its own scroll position.
 */

import React from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Appbar,
  Divider,
  Text,
} from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useBundleMyCompanyPayments, type MyCompanyPayment } from '@modules/bundles';

export default function CompanyPaymentsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const payments = useBundleMyCompanyPayments(id, 1, 50);

  const data = payments.data?.payments ?? [];

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={t('companies.payments.title')} />
      </Appbar.Header>

      {payments.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <FlatList
          style={styles.flex1}
          data={data}
          keyExtractor={(p) => p.id}
          renderItem={({ item }) => <PaymentRow payment={item} />}
          ItemSeparatorComponent={() => <Divider />}
          contentContainerStyle={{
            paddingTop: 8,
            paddingBottom: 24 + insets.bottom,
          }}
          ListEmptyComponent={
            <View style={styles.emptyWrap}>
              <MaterialCommunityIcons
                name="receipt-text-outline"
                size={56}
                color={colors.onSurfaceVariant}
              />
              <Text
                variant="bodyMedium"
                style={{ color: colors.onSurfaceVariant, marginTop: 12, textAlign: 'center' }}
              >
                {t('companies.payments.empty')}
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

function PaymentRow({ payment }: { payment: MyCompanyPayment }) {
  const { colors } = useAppTheme();
  return (
    <View style={styles.row}>
      <MaterialCommunityIcons name="receipt" size={20} color={colors.primary} />
      <View style={styles.rowBody}>
        <Text
          variant="bodyMedium"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: '500' }}
        >
          {payment.receipt_number ?? payment.reference}
        </Text>
        <Text
          variant="bodySmall"
          style={{ color: colors.onSurfaceVariant }}
          numberOfLines={1}
        >
          {payment.created_at ? new Date(payment.created_at).toLocaleDateString() : ''}
          {payment.entity_code ? ` · ${payment.entity_code}` : ''}
        </Text>
      </View>
      <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
        {payment.amount.toLocaleString()} {payment.currency}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  flex1: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyWrap: { paddingTop: 64, paddingHorizontal: 24, alignItems: 'center' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  rowBody: { flex: 1 },
});
