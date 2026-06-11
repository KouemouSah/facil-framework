import React from 'react';
import { StyleSheet, View } from 'react-native';
import { RadioButton, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import {
  ASSIGNABLE_MEMBER_ROLES,
  type AssignableMemberRole,
} from '../types/companies.types';

interface MemberRolePickerProps {
  value: AssignableMemberRole;
  onChange: (role: AssignableMemberRole) => void;
}

export function MemberRolePicker({ value, onChange }: MemberRolePickerProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      {ASSIGNABLE_MEMBER_ROLES.map((role) => (
        <View key={role} style={styles.row}>
          <RadioButton.Android
            value={role}
            status={value === role ? 'checked' : 'unchecked'}
            onPress={() => onChange(role)}
          />
          <View style={{ flex: 1 }}>
            <Text variant="titleSmall" style={{ color: colors.onSurface }}>
              {t(`companies.members.roles.${role}`)}
            </Text>
            <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
              {t(`companies.members.roleDescriptions.${role}`)}
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 8 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
});
