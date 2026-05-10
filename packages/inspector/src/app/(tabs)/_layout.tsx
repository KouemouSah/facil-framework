/**
 * Tab Navigator - Facil Inspeccion
 *
 * 4 tabs: Dashboard, Inspections, Verify, Profile
 */

import React from 'react';
import { Tabs } from 'expo-router';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { AuthGuard } from '@core/auth/auth-guard';
import { useAppTheme } from '@core/theme';

export default function TabLayout() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <AuthGuard>
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.onSurfaceVariant,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.outlineVariant,
            borderTopWidth: 0.5,
            elevation: 0,
            height: 56,
          },
          tabBarLabelStyle: { fontSize: 11, fontWeight: '600', marginBottom: 4 },
          tabBarIconStyle: { marginTop: 4 },
        }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: t('tabs.dashboard'),
            tabBarIcon: ({ color, size }) => (
              <MaterialCommunityIcons name="view-dashboard" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="inspections"
          options={{
            title: t('tabs.inspections'),
            tabBarIcon: ({ color, size }) => (
              <MaterialCommunityIcons name="clipboard-list" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="verify"
          options={{
            title: t('tabs.verify'),
            tabBarIcon: ({ color, size }) => (
              <MaterialCommunityIcons name="magnify-scan" size={size} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="profile"
          options={{
            title: t('tabs.profile'),
            tabBarIcon: ({ color, size }) => (
              <MaterialCommunityIcons name="account" size={size} color={color} />
            ),
          }}
        />
      </Tabs>
    </AuthGuard>
  );
}
