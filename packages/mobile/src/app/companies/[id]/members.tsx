import React, { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Appbar,
  Divider,
  FAB,
  Menu,
  Snackbar,
  Text,
} from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AddMemberSheet } from '@modules/companies/components/add-member-sheet';
import { MemberListItem } from '@modules/companies/components/member-list-item';
import {
  useAddMember,
  useCompanyDetail,
  useCompanyMembers,
  useRemoveMember,
  useUpdateMemberRole,
} from '@modules/companies';
import {
  ASSIGNABLE_MEMBER_ROLES,
  type AssignableMemberRole,
  type CompanyMember,
} from '@modules/companies';

export default function CompanyMembersScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const companyId = id ?? '';
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();
  const detail = useCompanyDetail(companyId || null);
  const members = useCompanyMembers(companyId || null);
  const add = useAddMember(companyId);
  const updateRole = useUpdateMemberRole(companyId);
  const remove = useRemoveMember(companyId);

  const [addVisible, setAddVisible] = useState(false);
  const [roleMenuFor, setRoleMenuFor] = useState<CompanyMember | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const handleAdd = useCallback(
    (payload: Parameters<typeof add.mutate>[0]) => {
      add.mutate(payload, {
        onSuccess: () => {
          setAddVisible(false);
          setSnackbar(t('companies.members.add.success'));
        },
        onError: (err) =>
          setSnackbar(err instanceof Error ? err.message : t('companies.errors.unknown')),
      });
    },
    [add, t],
  );

  const handleChangeRole = useCallback(
    (member: CompanyMember, role: AssignableMemberRole) => {
      updateRole.mutate(
        { memberUserId: member.user_id, payload: { role } },
        {
          onSuccess: () => {
            setRoleMenuFor(null);
            setSnackbar(t('companies.members.role.success'));
          },
          onError: (err) =>
            setSnackbar(err instanceof Error ? err.message : t('companies.errors.unknown')),
        },
      );
    },
    [updateRole, t],
  );

  const handleRemove = useCallback(
    (member: CompanyMember) => {
      Alert.alert(
        t('companies.members.remove.title'),
        t('companies.members.remove.body', {
          name: member.user_name ?? member.user_email ?? '—',
        }),
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('companies.members.remove.confirm'),
            style: 'destructive',
            onPress: () =>
              remove.mutate(member.user_id, {
                onSuccess: () => setSnackbar(t('companies.members.remove.success')),
                onError: (err) =>
                  setSnackbar(err instanceof Error ? err.message : t('companies.errors.unknown')),
              }),
          },
        ],
      );
    },
    [remove, t],
  );

  return (
    <SafeAreaView edges={['top']} style={[styles.root, { backgroundColor: colors.background }]}>
      <Stack.Screen options={{ headerShown: false }} />
      <Appbar.Header style={{ backgroundColor: colors.surface }}>
        <Appbar.BackAction onPress={() => router.back()} />
        <Appbar.Content
          title={t('companies.members.title')}
          subtitle={detail.data?.legal_name ?? ''}
        />
      </Appbar.Header>

      {members.isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : (
        <FlatList
          data={members.data ?? []}
          keyExtractor={(item) => item.user_id}
          renderItem={({ item }) => (
            <View>
              <Menu
                visible={roleMenuFor?.user_id === item.user_id}
                onDismiss={() => setRoleMenuFor(null)}
                anchor={
                  <MemberListItem
                    member={item}
                    onPress={
                      item.role === 'company_owner'
                        ? undefined
                        : (m) => setRoleMenuFor(m)
                    }
                  />
                }
              >
                {ASSIGNABLE_MEMBER_ROLES.map((role) => (
                  <Menu.Item
                    key={role}
                    title={t(`companies.members.roles.${role}`)}
                    onPress={() => handleChangeRole(item, role)}
                  />
                ))}
                <Divider />
                <Menu.Item
                  title={t('companies.members.remove.confirm')}
                  leadingIcon="trash-can-outline"
                  onPress={() => {
                    setRoleMenuFor(null);
                    handleRemove(item);
                  }}
                />
              </Menu>
            </View>
          )}
          ItemSeparatorComponent={() => <Divider />}
          contentContainerStyle={{ paddingBottom: 96 + insets.bottom }}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text variant="titleSmall" style={{ color: colors.onSurfaceVariant }}>
                {t('companies.detail.noMembers')}
              </Text>
            </View>
          }
        />
      )}

      <FAB
        icon="account-plus"
        style={[styles.fab, { backgroundColor: colors.primary, bottom: 16 + insets.bottom }]}
        color="white"
        onPress={() => setAddVisible(true)}
        accessibilityLabel={t('companies.members.add.title')}
      />

      <AddMemberSheet
        visible={addVisible}
        loading={add.isPending}
        onCancel={() => setAddVisible(false)}
        onSubmit={handleAdd}
      />

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  fab: { position: 'absolute', right: 16 },
});
