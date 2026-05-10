/**
 * Cookie Policy — informational only on mobile.
 *
 * No checkbox / consent UI : the mobile app does not use HTTP cookies the
 * way the web does. This page exists for parity with the web (Play Store
 * reviewers may check the listed Privacy URL, this page is reachable from
 * the Profile screen).
 */

import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

const COOKIES_SECTIONS = [
  'whatAre',
  'types',
  'purpose',
  'thirdParty',
  'management',
  'contact',
] as const;

export default function CookiesScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <>
      <Stack.Screen options={{ title: t('legal.cookies.title') }} />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={styles.content}
      >
        <Text
          variant="labelMedium"
          style={[styles.lastUpdated, { color: colors.onSurfaceVariant }]}
        >
          {t('legal.cookies.lastUpdated')}
        </Text>
        <Text variant="bodyLarge" style={[styles.intro, { color: colors.onSurface }]}>
          {t('legal.cookies.intro')}
        </Text>

        {COOKIES_SECTIONS.map((key, idx) => (
          <View key={key} style={styles.section}>
            <Text
              variant="titleMedium"
              style={[styles.sectionTitle, { color: colors.onSurface }]}
            >
              {idx + 1}. {t(`legal.cookies.${key}Title`)}
            </Text>
            <Text
              variant="bodyMedium"
              style={[styles.sectionBody, { color: colors.onSurfaceVariant }]}
            >
              {t(`legal.cookies.${key}Content`)}
            </Text>
          </View>
        ))}
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 16,
    paddingBottom: 32,
  },
  lastUpdated: {
    marginBottom: 8,
  },
  intro: {
    marginBottom: 24,
    lineHeight: 22,
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    marginBottom: 8,
    fontWeight: '600',
  },
  sectionBody: {
    lineHeight: 22,
  },
});
