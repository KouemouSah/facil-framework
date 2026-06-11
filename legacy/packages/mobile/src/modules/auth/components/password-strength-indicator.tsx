/**
 * Password Strength Indicator
 *
 * Visual feedback component showing password strength criteria.
 * Uses MD3 ProgressBar + checklist with color-coded states.
 *
 * Criteria (matching backend validate_password_strength):
 * - Min 8 characters
 * - 1 uppercase letter
 * - 1 lowercase letter
 * - 1 digit
 * - 1 special character
 */

import React, { useMemo } from 'react';
import { View, StyleSheet } from 'react-native';
import { Text, ProgressBar, useTheme } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { getPasswordStrength, type PasswordStrengthResult } from '../validations';

interface PasswordStrengthIndicatorProps {
  password: string;
}

export function PasswordStrengthIndicator({ password }: PasswordStrengthIndicatorProps) {
  const { t } = useTranslation();
  const theme = useTheme();

  const strength: PasswordStrengthResult = useMemo(
    () => getPasswordStrength(password),
    [password],
  );

  if (!password) return null;

  const progress = strength.score / 5;
  const color =
    strength.score <= 1
      ? theme.colors.error
      : strength.score <= 3
        ? theme.colors.tertiary
        : theme.colors.primary;

  const label =
    strength.score <= 1
      ? t('auth.passwordStrengthWeak')
      : strength.score <= 3
        ? t('auth.passwordStrengthMedium')
        : t('auth.passwordStrengthStrong');

  const criteriaItems: { key: keyof PasswordStrengthResult['criteria']; label: string }[] = [
    { key: 'minLength', label: t('auth.passwordRequirements.minLength') },
    { key: 'hasUppercase', label: t('auth.passwordRequirements.uppercase') },
    { key: 'hasLowercase', label: t('auth.passwordRequirements.lowercase') },
    { key: 'hasDigit', label: t('auth.passwordRequirements.digit') },
    { key: 'hasSpecial', label: t('auth.passwordRequirements.special') },
  ];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text variant="labelSmall" style={{ color: theme.colors.onSurfaceVariant }}>
          {t('auth.passwordStrength')}
        </Text>
        <Text variant="labelSmall" style={{ color }}>
          {label}
        </Text>
      </View>
      <ProgressBar
        progress={progress}
        color={color}
        style={styles.progressBar}
      />
      <View style={styles.criteria}>
        {criteriaItems.map(({ key, label: criterionLabel }) => (
          <View key={key} style={styles.criterionRow}>
            <Text
              variant="labelSmall"
              style={{
                color: strength.criteria[key]
                  ? theme.colors.primary
                  : theme.colors.onSurfaceVariant,
              }}
            >
              {strength.criteria[key] ? '✓' : '○'} {criterionLabel}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 4,
    gap: 4,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  progressBar: {
    height: 4,
    borderRadius: 2,
  },
  criteria: {
    gap: 2,
  },
  criterionRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
