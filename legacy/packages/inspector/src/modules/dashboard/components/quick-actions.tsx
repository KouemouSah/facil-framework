/**
 * Quick Actions — Compact chip-style buttons (Google Maps pattern)
 * Horizontal scroll, compact, one-tap access.
 */

import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';
import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';

interface ActionChip {
  icon: string;
  labelKey: string;
  onPress: () => void;
  primary?: boolean;
  supervisorOnly?: boolean;
}

export function QuickActions() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { isSupervisor } = useAuth();

  const actions: ActionChip[] = [
    {
      icon: 'qrcode-scan',
      labelKey: 'scanner.scanLicense',
      onPress: () => router.push({ pathname: '/(tabs)/verify', params: { openScanner: '1' } } as never),
      primary: true,
    },
    {
      icon: 'magnify',
      labelKey: 'dashboard.verifyLicense',
      onPress: () => router.push('/(tabs)/verify' as never),
    },
    {
      icon: 'clipboard-list-outline',
      labelKey: 'inspection.list',
      onPress: () => router.push('/(tabs)/inspections' as never),
    },
    {
      icon: 'shield-account',
      labelKey: 'supervisor.dashboard',
      onPress: () => router.push('/supervisor/' as never),
      supervisorOnly: true,
    },
  ];

  const visible = actions.filter((a) => !a.supervisorOnly || isSupervisor);

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {visible.map((action) => (
        <Pressable
          key={action.labelKey}
          onPress={action.onPress}
          style={({ pressed }) => [
            styles.chip,
            {
              backgroundColor: action.primary ? colors.primary : colors.surface,
              borderColor: action.primary ? colors.primary : colors.outlineVariant,
              opacity: pressed ? 0.8 : 1,
            },
          ]}
          android_ripple={{ color: action.primary ? '#FFFFFF33' : colors.surfaceVariant }}
        >
          <MaterialCommunityIcons
            name={action.icon as never}
            size={18}
            color={action.primary ? '#FFF' : colors.primary}
          />
          <Text
            variant="labelMedium"
            style={{ color: action.primary ? '#FFF' : colors.onSurface, marginLeft: 6 }}
            numberOfLines={1}
          >
            {t(action.labelKey)}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingBottom: 16,
    gap: 8,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
});
