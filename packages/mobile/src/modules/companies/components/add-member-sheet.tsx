import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import {
  Button,
  Dialog,
  HelperText,
  Portal,
  Text,
  TextInput,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import {
  ASSIGNABLE_MEMBER_ROLES,
  type AddMemberRequest,
  type AssignableMemberRole,
} from '../types/companies.types';
import { MemberRolePicker } from './member-role-picker';

interface AddMemberSheetProps {
  visible: boolean;
  loading?: boolean;
  onCancel: () => void;
  onSubmit: (payload: AddMemberRequest) => void;
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Add member sheet — backend takes a `member_user_id` UUID, NOT an email.
 * UI surfaces this constraint explicitly (helper text). A future backend
 * `/users/lookup-by-email` endpoint will let us replace the UUID input
 * with an email picker.
 */
export function AddMemberSheet({
  visible,
  loading,
  onCancel,
  onSubmit,
}: AddMemberSheetProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<AssignableMemberRole>(ASSIGNABLE_MEMBER_ROLES[0]);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = () => {
    const trimmed = userId.trim();
    if (!UUID_RE.test(trimmed)) {
      setError(t('companies.members.add.errors.invalidId'));
      return;
    }
    setError(null);
    onSubmit({ member_user_id: trimmed, role });
  };

  const handleCancel = () => {
    setUserId('');
    setRole(ASSIGNABLE_MEMBER_ROLES[0]);
    setError(null);
    onCancel();
  };

  return (
    <Portal>
      <Dialog visible={visible} onDismiss={handleCancel}>
        <Dialog.Title>{t('companies.members.add.title')}</Dialog.Title>
        <Dialog.Content>
          <View style={styles.section}>
            <TextInput
              label={t('companies.members.add.fields.userId')}
              value={userId}
              onChangeText={setUserId}
              mode="outlined"
              autoCapitalize="none"
              error={!!error}
            />
            {error ? (
              <HelperText type="error">{error}</HelperText>
            ) : (
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {t('companies.members.add.fields.userIdHelp')}
              </Text>
            )}
          </View>

          <View style={styles.section}>
            <Text variant="titleSmall" style={{ color: colors.onSurface, marginBottom: 8 }}>
              {t('companies.members.add.fields.role')}
            </Text>
            <MemberRolePicker value={role} onChange={setRole} />
          </View>
        </Dialog.Content>
        <Dialog.Actions>
          <Button onPress={handleCancel}>{t('common.cancel')}</Button>
          <Button onPress={handleSubmit} loading={loading} disabled={loading}>
            {t('companies.members.add.confirm')}
          </Button>
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: 16 },
});
