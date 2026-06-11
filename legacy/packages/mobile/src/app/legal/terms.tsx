/**
 * Terms of Service — full text rendering for mobile.
 *
 * Sections mirror web `/legal/terms/page.tsx`. See privacy.tsx for the
 * shared rendering approach.
 */

import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { Stack } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

const TERMS_SECTIONS = [
  'acceptance',
  'services',
  'account',
  'obligations',
  'intellectualProperty',
  'limitations',
  'modifications',
  'jurisdiction',
] as const;

export default function TermsScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <>
      <Stack.Screen options={{ title: t('legal.terms.title') }} />
      <ScrollView
        style={{ flex: 1, backgroundColor: colors.background }}
        contentContainerStyle={styles.content}
      >
        <Text
          variant="labelMedium"
          style={[styles.lastUpdated, { color: colors.onSurfaceVariant }]}
        >
          {t('legal.terms.lastUpdated')}
        </Text>
        <Text variant="bodyLarge" style={[styles.intro, { color: colors.onSurface }]}>
          {t('legal.terms.intro')}
        </Text>

        {TERMS_SECTIONS.map((key, idx) => (
          <View key={key} style={styles.section}>
            <Text
              variant="titleMedium"
              style={[styles.sectionTitle, { color: colors.onSurface }]}
            >
              {idx + 1}. {t(`legal.terms.${key}Title`)}
            </Text>
            <Text
              variant="bodyMedium"
              style={[styles.sectionBody, { color: colors.onSurfaceVariant }]}
            >
              {t(`legal.terms.${key}Content`)}
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
