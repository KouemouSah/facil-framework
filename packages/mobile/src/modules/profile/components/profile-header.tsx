/**
 * Profile Header — Compact Android 14+ style
 *
 * Displays avatar (with tap-to-change), full name, and role badge.
 * Email/phone removed (shown only in Personal Info section to avoid duplication).
 */

import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Text, Avatar, useTheme } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import type { UserProfile } from '@core/config/types';
import { getFullName } from '@core/config/types';

interface ProfileHeaderProps {
  user: UserProfile;
  onAvatarPress: () => void;
  isUploading?: boolean;
}

export function ProfileHeader({ user, onAvatarPress, isUploading }: ProfileHeaderProps) {
  const theme = useTheme();
  const { t } = useTranslation();

  const fullName = getFullName(user);
  const initials = fullName
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.surface }]}>
      <Pressable
        onPress={onAvatarPress}
        style={styles.avatarContainer}
        android_ripple={{ color: theme.colors.primaryContainer, borderless: true, radius: 36 }}
      >
        {user.avatar_url ? (
          <Avatar.Image size={64} source={{ uri: user.avatar_url }} />
        ) : (
          <Avatar.Text
            size={64}
            label={initials}
            style={{ backgroundColor: theme.colors.primaryContainer }}
            labelStyle={{ color: theme.colors.onPrimaryContainer }}
          />
        )}
        <View
          style={[styles.cameraOverlay, { backgroundColor: theme.colors.primary }]}
        >
          <MaterialCommunityIcons
            name={isUploading ? 'loading' : 'camera'}
            size={14}
            color={theme.colors.onPrimary}
          />
        </View>
      </Pressable>

      <View style={styles.textBlock}>
        <Text variant="titleLarge" style={[styles.name, { color: theme.colors.onSurface }]}>
          {fullName}
        </Text>
        <Text variant="bodySmall" style={{ color: theme.colors.outline }}>
          {t(`roles.${user.role_code ?? user.role}`)}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 16,
    gap: 16,
  },
  avatarContainer: {
    position: 'relative',
  },
  cameraOverlay: {
    position: 'absolute',
    bottom: -2,
    right: -2,
    width: 26,
    height: 26,
    borderRadius: 13,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'white',
  },
  textBlock: {
    flex: 1,
    gap: 2,
  },
  name: {
    fontWeight: '600',
  },
});
