/**
 * LegalAcceptanceCard — 2 mandatory checkboxes for ToS + Privacy at sign-up.
 *
 * Used inside the (auth)/sign-up screen. Renders 2 rows :
 *  - "J'accepte les Conditions Générales d'Utilisation"
 *  - "J'accepte la Politique de Confidentialité"
 * Each label includes a tappable link that pushes the corresponding stack
 * screen (`/legal/terms` / `/legal/privacy`).
 *
 * The submit button on the parent form must be disabled while either
 * checkbox is unchecked (controlled — the parent owns the boolean state).
 *
 * Accessibility : `Checkbox` from react-native-paper exposes a checkbox
 * role natively. The whole row is a Pressable so the touch target is
 * generous (full row height ≥ 48dp).
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Checkbox, Text } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

interface Props {
  termsAccepted: boolean;
  privacyAccepted: boolean;
  onTermsToggle: (next: boolean) => void;
  onPrivacyToggle: (next: boolean) => void;
  /** When set, both rows are disabled (e.g. during submit). */
  disabled?: boolean;
}

export function LegalAcceptanceCard({
  termsAccepted,
  privacyAccepted,
  onTermsToggle,
  onPrivacyToggle,
  disabled = false,
}: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  return (
    <View style={styles.container}>
      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: termsAccepted, disabled }}
        accessibilityLabel={t('legal.acceptance.termsAccessibility')}
        onPress={() => !disabled && onTermsToggle(!termsAccepted)}
        style={({ pressed }) => [
          styles.row,
          pressed && !disabled ? { backgroundColor: `${colors.primary}10` } : null,
          disabled ? styles.disabled : null,
        ]}
      >
        <Checkbox
          status={termsAccepted ? 'checked' : 'unchecked'}
          disabled={disabled}
        />
        <Text variant="bodyMedium" style={styles.label}>
          {t('legal.acceptance.termsPrefix')}{' '}
          <Text
            style={[styles.link, { color: colors.primary }]}
            onPress={() => router.push('/legal/terms' as never)}
          >
            {t('legal.acceptance.termsLink')}
          </Text>
        </Text>
      </Pressable>

      <Pressable
        accessibilityRole="checkbox"
        accessibilityState={{ checked: privacyAccepted, disabled }}
        accessibilityLabel={t('legal.acceptance.privacyAccessibility')}
        onPress={() => !disabled && onPrivacyToggle(!privacyAccepted)}
        style={({ pressed }) => [
          styles.row,
          pressed && !disabled ? { backgroundColor: `${colors.primary}10` } : null,
          disabled ? styles.disabled : null,
        ]}
      >
        <Checkbox
          status={privacyAccepted ? 'checked' : 'unchecked'}
          disabled={disabled}
        />
        <Text variant="bodyMedium" style={styles.label}>
          {t('legal.acceptance.privacyPrefix')}{' '}
          <Text
            style={[styles.link, { color: colors.primary }]}
            onPress={() => router.push('/legal/privacy' as never)}
          >
            {t('legal.acceptance.privacyLink')}
          </Text>
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginVertical: 8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 4,
    minHeight: 48,
    borderRadius: 4,
  },
  label: {
    flex: 1,
    marginLeft: 8,
  },
  link: {
    textDecorationLine: 'underline',
    fontWeight: '500',
  },
  disabled: {
    opacity: 0.5,
  },
});
