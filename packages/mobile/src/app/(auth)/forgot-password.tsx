/**
 * Forgot Password Screen
 *
 * Sends a password reset link to the user's email.
 * Wired to POST /auth/password/reset/request.
 *
 * Security: The success message does NOT reveal if the email exists.
 */

import { useState } from 'react';
import { StyleSheet, View, KeyboardAvoidingView, Platform } from 'react-native';
import { Text, TextInput, Button, Surface, HelperText } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAppTheme } from '@core/theme';
import {
  passwordResetRequestSchema,
  type PasswordResetRequestInput,
} from '@modules/auth/validations';
import { usePasswordResetRequest } from '@modules/auth/services/auth-hooks';

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [isSent, setIsSent] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<PasswordResetRequestInput>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: { email: '' },
  });

  const resetMutation = usePasswordResetRequest();

  const onSubmit = (data: PasswordResetRequestInput) => {
    setErrorMessage(null);
    resetMutation.mutate(data.email, {
      onSuccess: () => setIsSent(true),
      onError: () => {
        // Always show success message even on error (email enumeration protection).
        // The backend returns 200 regardless, but network errors should still
        // be visible to the user.
        setIsSent(true);
      },
    });
  };

  const handleResend = () => {
    setIsSent(false);
    resetMutation.mutate(getValues('email'), {
      onSuccess: () => setIsSent(true),
      onError: () => setIsSent(true),
    });
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={[styles.content, { paddingHorizontal: spacing.lg }]}>
          {/* Back button */}
          <Button
            mode="text"
            icon="arrow-left"
            onPress={() => router.back()}
            style={styles.backButton}
            compact
          >
            {t('common.back')}
          </Button>

          {/* Icon */}
          <View style={[styles.iconContainer, { marginBottom: spacing.lg }]}>
            <MaterialCommunityIcons
              name={isSent ? 'email-check-outline' : 'lock-reset'}
              size={64}
              color={colors.primary}
            />
          </View>

          {/* Title */}
          <Text
            variant="headlineSmall"
            style={[styles.title, { color: colors.onBackground, marginBottom: spacing.sm }]}
          >
            {t('auth.resetPassword')}
          </Text>

          {isSent ? (
            /* Success state — never reveals if email exists */
            <View style={[styles.successContainer, { marginTop: spacing.md }]}>
              <Text
                variant="bodyLarge"
                style={[
                  styles.successText,
                  { color: colors.onSurfaceVariant, marginTop: spacing.md },
                ]}
              >
                {t('auth.resetPasswordSent')}
              </Text>

              <Button
                mode="text"
                onPress={handleResend}
                loading={resetMutation.isPending}
                style={{ marginTop: spacing.md }}
              >
                {t('auth.resendCode')}
              </Button>

              <Button
                mode="contained"
                onPress={() => router.replace('/(auth)/sign-in')}
                style={{ marginTop: spacing.lg }}
                contentStyle={styles.buttonContent}
              >
                {t('auth.backToSignIn')}
              </Button>
            </View>
          ) : (
            /* Form */
            <Surface
              style={[
                styles.formCard,
                {
                  padding: spacing.lg,
                  borderRadius: borderRadius.lg,
                  backgroundColor: colors.surface,
                  marginTop: spacing.md,
                },
              ]}
              elevation={1}
            >
              <Text
                variant="bodyMedium"
                style={{ color: colors.onSurfaceVariant, marginBottom: spacing.lg, textAlign: 'center' }}
              >
                {t('auth.resetPasswordDescription')}
              </Text>

              <Controller
                control={control}
                name="email"
                render={({ field: { onChange, onBlur, value } }) => (
                  <View style={{ marginBottom: spacing.lg }}>
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
                loading={resetMutation.isPending}
                disabled={resetMutation.isPending}
                contentStyle={styles.buttonContent}
                style={{ borderRadius: borderRadius.sm }}
              >
                {t('auth.sendResetLink')}
              </Button>
            </Surface>
          )}
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
  backButton: {
    position: 'absolute',
    top: 0,
    left: 0,
  },
  iconContainer: {
    alignItems: 'center',
  },
  title: {
    fontWeight: '700',
    textAlign: 'center',
  },
  formCard: {
    width: '100%',
  },
  buttonContent: {
    paddingVertical: 6,
  },
  successContainer: {
    alignItems: 'center',
  },
  successText: {
    textAlign: 'center',
    lineHeight: 22,
  },
});
