/**
 * About screen — app version, copyright, contact, framework attribution.
 *
 * Reachable from Profile screen → "About / Acerca de" list item. Implements
 * the user-facing copyright placement (vs. on the Play Store feature graphic
 * — see Phase 10/E critique §6 for the design rationale).
 *
 * Phase 10/E v3 (2026-05-02).
 */

import React from 'react';
import { Linking, ScrollView, StyleSheet, View } from 'react-native';
import { Divider, List, Text } from 'react-native-paper';
import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';
import Constants from 'expo-constants';

import { useAppTheme } from '@core/theme';
import { appConfig } from '@core/config/app';

const COPYRIGHT_HOLDER = 'KOUEMOU SAH Jean Emac';
const COPYRIGHT_EMAIL = 'kouemou.sah@gmail.com';
const FRAMEWORK_REPO_URL = 'https://github.com/KouemouSah/taxasge';

export default function AboutScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const version = Constants.expoConfig?.version ?? appConfig.app.version;
  const buildNumber =
    Constants.expoConfig?.android?.versionCode?.toString() ??
    Constants.expoConfig?.ios?.buildNumber ??
    'dev';
  const currentYear = new Date().getFullYear();

  const handleEmailPress = () => {
    Linking.openURL(`mailto:${COPYRIGHT_EMAIL}?subject=Facil%20mobile%20app`);
  };

  const handleRepoPress = () => {
    Linking.openURL(FRAMEWORK_REPO_URL);
  };

  return (
    <>
      <Stack.Screen options={{ title: t('settings.about.title', { defaultValue: 'About' }) }} />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={styles.content}
      >
        {/* App identity */}
        <View style={styles.brandSection}>
          <Text variant="headlineMedium" style={[styles.appName, { color: colors.primary }]}>
            Facil
          </Text>
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
            {t('settings.about.tagline', {
              defaultValue: 'Adaptable framework for digitizing administrative procedures',
            })}
          </Text>
        </View>

        <Divider />

        {/* Version + build */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Item
            title={t('settings.about.version', { defaultValue: 'Version' })}
            description={`${version} (build ${buildNumber})`}
            left={(props) => <List.Icon {...props} icon="information-outline" />}
          />
        </View>

        <Divider />

        {/* Current deployment instance */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.about.deployment', { defaultValue: 'Current deployment' })}
          </List.Subheader>
          <List.Item
            title={t('settings.about.country', { defaultValue: 'Republic of Equatorial Guinea' })}
            description={t('settings.about.partner', {
              defaultValue: 'In partnership with the General Directorate of Taxes (DGI)',
            })}
            left={(props) => <List.Icon {...props} icon="earth" />}
          />
        </View>

        <Divider />

        {/* Framework + author */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.about.framework', { defaultValue: 'Framework' })}
          </List.Subheader>
          <List.Item
            title={t('settings.about.author', { defaultValue: 'Author' })}
            description={COPYRIGHT_HOLDER}
            left={(props) => <List.Icon {...props} icon="account-outline" />}
          />
          <List.Item
            title={t('settings.about.contact', { defaultValue: 'Contact' })}
            description={COPYRIGHT_EMAIL}
            left={(props) => <List.Icon {...props} icon="email-outline" />}
            right={(props) => <List.Icon {...props} icon="open-in-new" />}
            onPress={handleEmailPress}
          />
          <List.Item
            title={t('settings.about.repo', { defaultValue: 'Source repository' })}
            description="github.com/KouemouSah/taxasge"
            left={(props) => <List.Icon {...props} icon="github" />}
            right={(props) => <List.Icon {...props} icon="open-in-new" />}
            onPress={handleRepoPress}
          />
        </View>

        <Divider />

        {/* Copyright + license */}
        <View style={[styles.legalSection, { backgroundColor: colors.surface }]}>
          <Text variant="bodySmall" style={[styles.copyright, { color: colors.onSurfaceVariant }]}>
            © {currentYear} {COPYRIGHT_HOLDER}.{' '}
            {t('settings.about.copyrightSuffix', { defaultValue: 'All rights reserved.' })}
          </Text>
          <Text variant="bodySmall" style={[styles.copyright, { color: colors.onSurfaceVariant, marginTop: 8 }]}>
            {t('settings.about.licenseNote', {
              defaultValue:
                'Facil is a proprietary framework. The current deployment instance is operated for the Republic of Equatorial Guinea.',
            })}
          </Text>
        </View>

        {/* Tech stack credits (optional, footer) */}
        <View style={styles.creditsFooter}>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant, textAlign: 'center' }}>
            {t('settings.about.builtWith', { defaultValue: 'Built with' })}{' '}
            React Native · Expo SDK 54 · FastAPI · PostgreSQL · Gemini 2.5
          </Text>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingBottom: 32,
  },
  brandSection: {
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
  appName: {
    fontWeight: '700',
    marginBottom: 4,
  },
  legalSection: {
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  copyright: {
    lineHeight: 18,
  },
  creditsFooter: {
    paddingHorizontal: 20,
    paddingVertical: 24,
  },
});
