import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type { CompanyMember, CompanyMemberRole } from '../types/companies.types';

interface MemberListItemProps {
  member: CompanyMember;
  onPress?: (member: CompanyMember) => void;
}

const ROLE_COLOR: Record<string, string> = {
  company_owner: '#1565C0',
  company_admin: '#7B1FA2',
  company_accountant: '#F57C00',
  company_member: '#388E3C',
};

function initialsOf(name?: string | null, email?: string | null): string {
  const source = (name ?? email ?? '?').trim();
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}

export function MemberListItem({ member, onPress }: MemberListItemProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const role = member.role as CompanyMemberRole;
  const roleColor = ROLE_COLOR[role] ?? ROLE_COLOR.company_member;
  const initials = initialsOf(member.user_name, member.user_email);

  return (
    <Pressable
      onPress={onPress ? () => onPress(member) : undefined}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[styles.row, { backgroundColor: colors.surface }]}
    >
      <View style={[styles.avatar, { backgroundColor: `${roleColor}26` }]}>
        <Text style={{ color: roleColor, fontWeight: '700' }}>{initials}</Text>
      </View>
      <View style={styles.body}>
        <Text variant="titleSmall" numberOfLines={1} style={{ color: colors.onSurface }}>
          {member.user_name ?? member.user_email ?? '—'}
        </Text>
        <Text variant="bodySmall" numberOfLines={1} style={{ color: colors.onSurfaceVariant }}>
          {member.user_email ?? ''}
        </Text>
      </View>
      <View style={[styles.roleBadge, { backgroundColor: `${roleColor}26` }]}>
        <Text style={{ color: roleColor, fontSize: 11, fontWeight: '700' }}>
          {t(`companies.members.roles.${role}`)}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 64,
    alignItems: 'center',
    gap: 12,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1 },
  roleBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
});
