/**
 * Privacy Policy — full text rendering for mobile.
 *
 * Sections are pulled from i18n keys `legal.privacy.<sectionKey>{Title,Content}`.
 * Sections list mirrors the web `/legal/privacy/page.tsx` reference but
 * adapted for mobile (ScrollView + plain text, no HTML).
 */

import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

const PRIVACY_SECTIONS = [
  'dataCollected',
  'purpose',
  'legalBasis',
  'retention',
  'sharing',
  'rights',
  'security',
  'contact',
] as const;

export default function PrivacyScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <>
      <Stack.Screen options={{ title: t('legal.privacy.title') }} />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={styles.content}
      >
        <Text
          variant="labelMedium"
          style={[styles.lastUpdated, { color: colors.onSurfaceVariant }]}
        >
          {t('legal.privacy.lastUpdated')}
        </Text>
        <Text variant="bodyLarge" style={[styles.intro, { color: colors.onSurface }]}>
          {t('legal.privacy.intro')}
        </Text>

        {PRIVACY_SECTIONS.map((key, idx) => (
          <View key={key} style={styles.section}>
            <Text
              variant="titleMedium"
              style={[styles.sectionTitle, { color: colors.onSurface }]}
            >
              {idx + 1}. {t(`legal.privacy.${key}Title`)}
            </Text>
            <Text
              variant="bodyMedium"
              style={[styles.sectionBody, { color: colors.onSurfaceVariant }]}
            >
              {t(`legal.privacy.${key}Content`)}
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
