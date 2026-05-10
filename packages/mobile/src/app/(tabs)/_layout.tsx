/**
 * Tab Navigator Layout — Dual mode (public / authenticated)
 *
 * Public mode (not logged in):
 *   Home | Services | Chat | Guide | Account
 *
 * Auth mode (logged in):
 *   Home | Services | Requests | Chat | Profile
 *
 * AuthGuard is NOT here — it's on individual protected screens.
 * Tabs are shown/hidden via `href: null` based on auth state.
 */

import { Tabs } from 'expo-router';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';

export default function TabLayout() {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.onSurfaceVariant,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.outlineVariant,
        },
        headerShown: false,
      }}
    >
      {/* ── Tab 1: Home (both modes) ── */}
      <Tabs.Screen
        name="index"
        options={{
          title: isAuthenticated ? t('dashboard.title') : t('home.title'),
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="home" size={size} color={color} />
          ),
        }}
      />

      {/* ── Tab 2: Services (both modes) ── */}
      <Tabs.Screen
        name="services"
        options={{
          title: t('services.title'),
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="magnify" size={size} color={color} />
          ),
        }}
      />

      {/* ── Tab 3a: Requests (auth only) ── */}
      <Tabs.Screen
        name="requests"
        options={{
          title: t('requests.title'),
          href: isAuthenticated ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons
              name="file-document-outline"
              size={size}
              color={color}
            />
          ),
        }}
      />

      {/* ── Tab 3b/4: Chat (both modes) ── */}
      <Tabs.Screen
        name="chat"
        options={{
          title: t('chat.title'),
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="star-four-points" size={size} color={color} />
          ),
        }}
      />

      {/* ── Tab 4 (public only): Guide ── */}
      <Tabs.Screen
        name="guide"
        options={{
          title: t('guide.title'),
          href: isAuthenticated ? null : undefined,
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="book-open-outline" size={size} color={color} />
          ),
        }}
      />

      {/* ── Tab 5a (public only): Account (login/register CTA) ── */}
      <Tabs.Screen
        name="account"
        options={{
          title: t('account.title'),
          href: isAuthenticated ? null : undefined,
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="account-outline" size={size} color={color} />
          ),
        }}
      />

      {/* ── Tab 5b (auth only): Profile ── */}
      <Tabs.Screen
        name="profile"
        options={{
          title: t('profile.title'),
          href: isAuthenticated ? undefined : null,
          tabBarIcon: ({ color, size }) => (
            <MaterialCommunityIcons name="account-outline" size={size} color={color} />
          ),
        }}
      />

      {/* ── Hidden: Payments stack (reached from profile, request detail, wizard) ── */}
      <Tabs.Screen
        name="payments"
        options={{
          href: null,
          title: t('payments.tabs.title'),
        }}
      />
    </Tabs>
  );
}
