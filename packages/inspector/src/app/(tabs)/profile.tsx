import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Divider, List, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '@core/hooks/use-auth';
import { useAppTheme } from '@core/theme';
import { getFullName } from '@core/config/types';
import { appConfig } from '@core/config/app';
import { changeLanguage } from '@core/i18n';

export default function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const { user, signOut, isSupervisor } = useAuth();
  const { colors } = useAppTheme();
  const insets = useSafeAreaInsets();

  const handleLanguage = () => {
    const langs = ['es', 'fr', 'en'];
    const current = langs.indexOf(i18n.language);
    const next = langs[(current + 1) % langs.length];
    changeLanguage(next);
  };

  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <Text variant="headlineSmall" style={{ color: colors.primary }}>
          {t('profile.title')}
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.surface }]}>
        <Text variant="titleMedium">{user ? getFullName(user) : '-'}</Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
          {user?.email}
        </Text>
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: 4 }}>
          {user?.role_code} {isSupervisor ? `(${t('role.supervisor')})` : `(${t('role.agent')})`}
        </Text>
      </View>

      <List.Section>
        <List.Item
          title={t('profile.entity')}
          description={user?.entity_name ?? '-'}
          left={(props) => <List.Icon {...props} icon="office-building" />}
        />
        <Divider />
        <List.Item
          title={t('profile.language')}
          description={i18n.language.toUpperCase()}
          left={(props) => <List.Icon {...props} icon="translate" />}
          onPress={handleLanguage}
        />
        <Divider />
        <List.Item
          title={t('profile.version')}
          description={`v${appConfig.app.version}`}
          left={(props) => <List.Icon {...props} icon="information" />}
        />
      </List.Section>

      <View style={styles.footer}>
        <Button mode="outlined" onPress={() => signOut()} textColor={colors.error}>
          {t('auth.signOut')}
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  header: { paddingHorizontal: 16, paddingBottom: 12 },
  card: { margin: 16, padding: 16, borderRadius: 12, elevation: 1 },
  footer: { padding: 16, marginTop: 'auto' },
});
