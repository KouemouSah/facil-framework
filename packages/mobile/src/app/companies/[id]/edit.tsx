import React, { useCallback, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Appbar, Snackbar, Text } from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { CompanyForm } from '@modules/companies/components/company-form';
import { useCompanyDetail, useUpdateCompany } from '@modules/companies';
import type {
  CompanyFormValues,
  CompanyUpdate,
  RegimenFiscal,
} from '@modules/companies';

export default function CompanyEditScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const detail = useCompanyDetail(id ?? null);
  const update = useUpdateCompany();
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const defaults: Partial<CompanyFormValues> | undefined = useMemo(() => {
    const d = detail.data;
    if (!d) return undefined;
    return {
      legal_name: d.legal_name,
      tax_id: d.tax_id ?? '',
      representante_legal: d.representante_legal ?? '',
      regimen_fiscal: (d.regimen_fiscal as RegimenFiscal) ?? null,
      zone_id: d.zone_id ?? null,
      commerce_type: d.commerce_type ?? null,
      forma_juridica: d.forma_juridica ?? null,
      sector_actividad: d.sector_actividad ?? null,
      address: d.address ?? null,
      email: d.email ?? null,
      phone: d.phone ?? null,
    };
  }, [detail.data]);

  const handleSubmit = useCallback(
    (values: CompanyFormValues) => {
      if (!id) return;
      // representante_legal is in CompanyCreate but NOT CompanyUpdate; the
      // backend treats it as immutable post-create. Skip it from the patch.
      // tax_id is also missing from CompanyUpdate — same reason (NIF/CIF
      // is identity, immutable).
      const patch: CompanyUpdate = {
        legal_name: values.legal_name,
        regimen_fiscal: values.regimen_fiscal ?? null,
        ...(values.zone_id !== undefined ? { zone_id: values.zone_id } : {}),
        ...(values.commerce_type !== undefined ? { commerce_type: values.commerce_type } : {}),
        ...(values.forma_juridica !== undefined ? { forma_juridica: values.forma_juridica } : {}),
        ...(values.sector_actividad !== undefined
          ? { sector_actividad: values.sector_actividad }
          : {}),
        ...(values.address !== undefined ? { address: values.address } : {}),
        ...(values.email !== undefined ? { email: values.email } : {}),
        ...(values.phone !== undefined ? { phone: values.phone } : {}),
      };
      update.mutate(
        { id, patch },
        {
          onSuccess: () => router.back(),
          onError: (err) =>
            setSnackbar(err instanceof Error ? err.message : t('companies.errors.unknown')),
        },
      );
    },
    [id, update, t],
  );

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content title={t('companies.edit.title')} />
      </Appbar.Header>

      {detail.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : !detail.data ? (
        <View style={styles.center}>
          <Text variant="titleSmall" style={{ color: colors.error }}>
            {t('companies.detail.loadError')}
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={[styles.content, { paddingBottom: 32 + insets.bottom }]}>
          <CompanyForm
            defaultValues={defaults}
            submitting={update.isPending}
            onSubmit={handleSubmit}
            submitLabelKey="companies.edit.action"
          />
        </ScrollView>
      )}

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: 16, paddingBottom: 32 },
});
