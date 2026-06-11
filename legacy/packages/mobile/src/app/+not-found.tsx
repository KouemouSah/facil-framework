/**
 * 404 — Not Found Screen
 *
 * Displayed when the user navigates to a route that does not exist.
 * Provides a clear message and a button to return to the home screen.
 */

import { StyleSheet, View } from 'react-native';
import { Text, Button } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

export default function NotFoundScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <View style={styles.content}>
        <MaterialCommunityIcons
          name="map-marker-question-outline"
          size={80}
          color={colors.outlineVariant}
        />
        <Text
          variant="headlineMedium"
          style={[styles.title, { color: colors.onBackground, marginTop: spacing.lg }]}
        >
          404
        </Text>
        <Text
          variant="bodyLarge"
          style={[styles.description, { color: colors.onSurfaceVariant, marginTop: spacing.sm }]}
        >
          {t('errors.notFound')}
        </Text>
        <Button
          mode="contained"
          onPress={() => router.replace('/')}
          style={{ marginTop: spacing.xl }}
        >
          {t('common.back')}
        </Button>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  title: {
    fontWeight: '700',
    textAlign: 'center',
  },
  description: {
    textAlign: 'center',
  },
});
