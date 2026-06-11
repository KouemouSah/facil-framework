/**
 * Sign In Screen
 *
 * Login form with email + password fields.
 * Uses react-hook-form + Zod validation aligned with backend LoginRequest.
 * Wired to AuthProvider signIn flow with 2FA support.
 */

import { useState, useEffect, useCallback } from 'react';
import { StyleSheet, View, KeyboardAvoidingView, Platform, Pressable, Alert, BackHandler } from 'react-native';
import { Image } from 'expo-image';
import { Text, TextInput, Button, Surface, HelperText, Divider } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, Link } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { extractApiError } from '@core/api/errors';
import { loginSchema, type LoginInput } from '@modules/auth/validations';
import {
  isBiometricAvailable,
  hasBiometricCredentials,
  getBiometricCredentials,
  saveBiometricCredentials,
} from '@core/security/biometric-login';

export default function SignInScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const { signIn } = useAuth();

  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showBiometric, setShowBiometric] = useState(false);
  const [biometricLoading, setBiometricLoading] = useState(false);

  // Back button → go to home instead of closing app
  useEffect(() => {
    const handler = BackHandler.addEventListener('hardwareBackPress', () => {
      router.replace('/(tabs)');
      return true; // prevent default (close app)
    });
    return () => handler.remove();
  }, [router]);

  // Check if biometric quick login is available
  useEffect(() => {
    (async () => {
      const available = await isBiometricAvailable();
      if (!available) return;
      const hasCreds = await hasBiometricCredentials();
      setShowBiometric(hasCreds);
    })();
  }, []);

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = async (data: LoginInput) => {
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      const result = await signIn(data.email, data.password);
      if (result.type === 'requires_2fa') {
        router.push({
          pathname: '/(auth)/verify-otp',
          params: { tempToken: result.tempToken },
        });
      } else {
        // Save credentials for biometric login (prompt only on first success)
        const available = await isBiometricAvailable();
        if (available) {
          const hasCreds = await hasBiometricCredentials();
          if (!hasCreds) {
            Alert.alert(
              t('auth.enableBiometric'),
              t('auth.enableBiometricDesc'),
              [
                { text: t('common.no'), style: 'cancel' },
                { text: t('common.yes'), onPress: () => saveBiometricCredentials(data.email, data.password) },
              ],
            );
          } else {
            // Update stored credentials silently
            await saveBiometricCredentials(data.email, data.password);
          }
        }
        router.replace('/(tabs)');
      }
    } catch (error) {
      const apiError = extractApiError(error);
      setErrorMessage(t(apiError.i18nKey));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleBiometricLogin = useCallback(async () => {
    setBiometricLoading(true);
    setErrorMessage(null);
    try {
      const creds = await getBiometricCredentials();
      if (!creds) {
        setBiometricLoading(false);
        return; // User cancelled or failed
      }
      const result = await signIn(creds.email, creds.password);
      if (result.type === 'requires_2fa') {
        router.push({
          pathname: '/(auth)/verify-otp',
          params: { tempToken: result.tempToken },
        });
      } else {
        router.replace('/(tabs)');
      }
    } catch (error) {
      const apiError = extractApiError(error);
      setErrorMessage(t(apiError.i18nKey));
    } finally {
      setBiometricLoading(false);
    }
  }, [signIn, router]);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={[styles.content, { paddingHorizontal: spacing.lg }]}>
          {/* Header */}
          <View style={[styles.header, { marginBottom: spacing.xl }]}>
            <Image
              source={require('../../../assets/images/logo_hd.png')}
              style={styles.logo}
              contentFit="contain"
              cachePolicy="memory-disk"
              transition={150}
            />
            <Text
              variant="bodyLarge"
              style={[styles.subtitle, { color: colors.onSurfaceVariant, marginTop: spacing.sm }]}
            >
              {t('auth.welcomeBack')}
            </Text>
          </View>

          {/* Form */}
          <Surface
            style={[
              styles.formCard,
              {
                padding: spacing.lg,
                borderRadius: borderRadius.lg,
                backgroundColor: colors.surface,
              },
            ]}
            elevation={1}
          >
            <Controller
              control={control}
              name="email"
              render={({ field: { onChange, onBlur, value } }) => (
                <View style={{ marginBottom: spacing.md }}>
                  <TextInput
                    label={t('auth.email')}
                    value={value}
                    onChangeText={onChange}
                    onBlur={onBlur}
                    mode="outlined"
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoComplete="email"
                    error={!!errors.email}
                    left={<TextInput.Icon icon="email-outline" />}
                  />
                  {errors.email && (
                    <HelperText type="error" visible>
                      {t(errors.email.message ?? 'auth.invalidEmail')}
                    </HelperText>
                  )}
                </View>
              )}
            />

            <Controller
              control={control}
              name="password"
              render={({ field: { onChange, onBlur, value } }) => (
                <View style={{ marginBottom: spacing.sm }}>
                  <TextInput
                    label={t('auth.password')}
                    value={value}
                    onChangeText={onChange}
                    onBlur={onBlur}
                    mode="outlined"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    error={!!errors.password}
                    left={<TextInput.Icon icon="lock-outline" />}
                    right={
                      <TextInput.Icon
                        icon={showPassword ? 'eye-off' : 'eye'}
                        onPress={() => setShowPassword(!showPassword)}
                      />
                    }
                  />
                  {errors.password && (
                    <HelperText type="error" visible>
                      {t(errors.password.message ?? 'auth.passwordRequired')}
                    </HelperText>
                  )}
                </View>
              )}
            />

            <Link
              href="/(auth)/forgot-password"
              style={[
                styles.forgotLink,
                { color: colors.primary, marginBottom: spacing.lg },
              ]}
            >
              {t('auth.forgotPassword')}
            </Link>

            {errorMessage && (
              <Text
                variant="bodySmall"
                style={{ color: colors.error, marginBottom: spacing.md, textAlign: 'center' }}
              >
                {errorMessage}
              </Text>
            )}

            <Button
              mode="contained"
              onPress={handleSubmit(onSubmit)}
              loading={isSubmitting}
              disabled={isSubmitting}
              contentStyle={styles.buttonContent}
              style={{ borderRadius: borderRadius.sm }}
            >
              {t('auth.signIn')}
            </Button>
          </Surface>

          {/* Biometric login button */}
          {showBiometric && (
            <View style={{ alignItems: 'center', marginTop: spacing.md }}>
              <Divider style={{ width: '60%', marginBottom: spacing.md }} />
              <Pressable
                onPress={handleBiometricLogin}
                disabled={biometricLoading}
                style={styles.biometricBtn}
                android_ripple={{ color: colors.primaryContainer }}
              >
                <MaterialCommunityIcons name="fingerprint" size={32} color={colors.primary} />
                <Text variant="labelMedium" style={{ color: colors.primary, marginTop: 4 }}>
                  {t('auth.biometricLogin')}
                </Text>
              </Pressable>
            </View>
          )}

          {/* Sign up link */}
          <View style={[styles.footer, { marginTop: spacing.lg }]}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('auth.noAccount')}{' '}
            </Text>
            <Link href="/(auth)/sign-up">
              <Text variant="bodyMedium" style={{ color: colors.primary, fontWeight: '600' }}>
                {t('auth.signUp')}
              </Text>
            </Link>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  keyboardView: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
  },
  logo: {
    width: 180,
    height: 80,
  },
  subtitle: {
    textAlign: 'center',
  },
  formCard: {
    width: '100%',
  },
  forgotLink: {
    textAlign: 'right',
    fontSize: 14,
  },
  buttonContent: {
    paddingVertical: 6,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  biometricBtn: {
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 16,
  },
});
