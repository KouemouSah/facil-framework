import React from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { Text, Surface, useTheme } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

export function QuickActions() {
  const theme = useTheme();
  const { t } = useTranslation();
  const router = useRouter();

  const actions = [
    { icon: 'plus-circle-outline', label: t('dashboard.quickActions.newRequest'), route: '/wizard/select-workflow' as const },
    { icon: 'file-document-multiple-outline', label: t('dashboard.quickActions.myRequests'), route: '/(tabs)/requests' as const },
    { icon: 'folder-outline', label: t('dashboard.quickActions.myDocuments'), route: '/documents' as const },
    { icon: 'domain', label: t('dashboard.quickActions.myCompanies'), route: '/companies' as const },
    { icon: 'headset', label: t('dashboard.quickActions.support'), route: '/support' as const },
  ];

  return (
    <View style={styles.row}>
      {actions.map((action) => (
        <Pressable
          key={action.route}
          onPress={() => router.push(action.route)}
          style={({ pressed }) => [styles.action, pressed && { opacity: 0.7 }]}
        >
          <Surface style={[styles.iconWrap, { backgroundColor: theme.colors.primaryContainer }]} elevation={0}>
            <MaterialCommunityIcons name={action.icon as keyof typeof MaterialCommunityIcons.glyphMap} size={24} color={theme.colors.primary} />
          </Surface>
          <Text variant="labelSmall" style={{ color: theme.colors.onSurface, textAlign: 'center' }} numberOfLines={2}>
            {action.label}
          </Text>
        </Pressable>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: 12 },
  action: { flex: 1, alignItems: 'center', gap: 6 },
  iconWrap: { width: 56, height: 56, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
});
