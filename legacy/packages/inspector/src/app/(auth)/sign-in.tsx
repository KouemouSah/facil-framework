/**
 * Sign In Screen - Facil Inspeccion
 *
 * Email/password login with biometric option.
 * Verifies inspection permissions after login.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import { Button, HelperText, IconButton, Text, TextInput } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@core/hooks/use-auth';
import { useAppTheme } from '@core/theme';
import { extractApiError } from '@core/api/errors';
import {
  getBiometricToken,
  hasBiometricCredentials,
  isBiometricAvailable,
} from '@core/security/biometric-login';
import { appConfig } from '@core/config/app';

export default function SignInScreen() {
  const { t } = useTranslation();
  const { signIn, signInWithBiometric, isAuthenticated, isLoading: authLoading } = useAuth();
  const theme = useAppTheme();
  const { colors } = theme;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [bioAvailable, setBioAvailable] = useState(false);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      router.replace('/(tabs)');
    }
  }, [isAuthenticated, authLoading]);

  useEffect(() => {
    async function checkBio() {
      const available = await isBiometricAvailable();
      const hasCredentials = await hasBiometricCredentials();
      setBioAvailable(available && hasCredentials);
    }
    checkBio();
  }, []);

  const handleSignIn = useCallback(async () => {
    if (!email.trim() || !password.trim()) return;
    setError('');
    setIsSubmitting(true);

    try {
      const result = await signIn(email.trim(), password);
      if (result.requires2fa) {
        router.push({
          pathname: '/(auth)/verify-2fa',
          params: { temp_token: result.tempToken, email: email.trim() },
        });
      } else {
        // Biometric token saved automatically by auth-provider
        router.replace('/(tabs)');
      }
    } catch (err) {
      const apiError = extractApiError(err);
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  }, [email, password, signIn]);

  const handleBiometric = useCallback(async () => {
    setError('');
    try {
      const biometric = await getBiometricToken();
      if (!biometric) return;

      setIsSubmitting(true);
      await signInWithBiometric(biometric.refreshToken, biometric.email);
      router.replace('/(tabs)');
    } catch (err) {
      const apiError = extractApiError(err);
      setError(apiError.message);
    } finally {
      setIsSubmitting(false);
    }
  }, [signInWithBiometric]);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <View style={styles.content}>
        <View style={styles.header}>
          <Image
            source={require('../../../assets/images/icon_facil.png')}
            style={styles.logo}
            resizeMode="contain"
          />
          <Text variant="headlineMedium" style={[styles.title, { color: colors.primary }]}>
            FACIL INSPECCION
          </Text>
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
            {t('app.tagline')}
          </Text>
        </View>

        <View style={styles.form}>
          <TextInput
            label={t('auth.email')}
            value={email}
            onChangeText={setEmail}
            keyboardType="email-address"
            autoCapitalize="none"
            autoComplete="email"
            mode="outlined"
            disabled={isSubmitting}
            style={styles.input}
          />

          <TextInput
            label={t('auth.password')}
            value={password}
            onChangeText={setPassword}
            secureTextEntry={!showPassword}
            autoCapitalize="none"
            mode="outlined"
            disabled={isSubmitting}
            style={styles.input}
            right={
              <TextInput.Icon
                icon={showPassword ? 'eye-off' : 'eye'}
                onPress={() => setShowPassword(!showPassword)}
              />
            }
          />

          {error ? (
            <HelperText type="error" visible={!!error}>{error}</HelperText>
          ) : null}

          <Button
            mode="contained"
            onPress={handleSignIn}
            loading={isSubmitting}
            disabled={isSubmitting || !email.trim() || !password.trim()}
            style={styles.button}
          >
            {isSubmitting ? t('auth.signingIn') : t('auth.signIn')}
          </Button>

          {bioAvailable && (
            <View style={styles.bioContainer}>
              <IconButton
                icon="fingerprint"
                size={48}
                iconColor={colors.primary}
                onPress={handleBiometric}
                disabled={isSubmitting}
              />
              <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                {t('auth.biometric')}
              </Text>
            </View>
          )}
        </View>

        <Text variant="labelSmall" style={[styles.version, { color: colors.onSurfaceVariant }]}>
          v{appConfig.app.version} • {__DEV__ ? 'dev' : 'prod'}
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', padding: 24 },
  header: { alignItems: 'center', marginBottom: 40 },
  logo: { width: 80, height: 80, marginBottom: 16 },
  title: { fontWeight: '900', marginBottom: 4, letterSpacing: 1 },
  form: { gap: 12 },
  input: { backgroundColor: 'transparent' },
  button: { marginTop: 8, paddingVertical: 4 },
  bioContainer: { alignItems: 'center', marginTop: 16 },
  version: { textAlign: 'center', marginTop: 32 },
});
