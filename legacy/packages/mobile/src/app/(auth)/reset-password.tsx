/**
 * Reset Password Screen
 *
 * Accessible via deep link: facil://reset-password?token=XXX
 * User enters new password + confirmation.
 * Wired to POST /auth/password/reset/confirm.
 */

import { useState } from 'react';
import { StyleSheet, View, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import { Text, TextInput, Button, Surface, HelperText } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAppTheme } from '@core/theme';
import {
  passwordResetConfirmSchema,
  type PasswordResetConfirmInput,
} from '@modules/auth/validations';
import { usePasswordResetConfirm } from '@modules/auth/services/auth-hooks';
import { PasswordStrengthIndicator } from '@modules/auth/components/password-strength-indicator';

export default function ResetPasswordScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const { token } = useLocalSearchParams<{ token: string }>();

  const [showPassword, setShowPassword] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<PasswordResetConfirmInput>({
    resolver: zodResolver(passwordResetConfirmSchema),
    defaultValues: {
      token: token ?? '',
      new_password: '',
      confirm_password: '',
    },
  });

  const confirmMutation = usePasswordResetConfirm();
  const watchPassword = watch('new_password');

  const onSubmit = (data: PasswordResetConfirmInput) => {
    setErrorMessage(null);
    confirmMutation.mutate(
      { token: data.token, newPassword: data.new_password },
      {
        onSuccess: () => setIsSuccess(true),
        onError: (error) => {
          // Token expired or invalid
          const message =
            error instanceof Error ? error.message : t('auth.resetTokenInvalid');
          setErrorMessage(message);
        },
      },
    );
  };

  if (!token) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.centerContent}>
          <MaterialCommunityIcons name="link-off" size={64} color={colors.error} />
          <Text
            variant="bodyLarge"
            style={{ color: colors.onSurfaceVariant, marginTop: spacing.lg, textAlign: 'center' }}
          >
            {t('auth.resetTokenMissing')}
          </Text>
          <Button
            mode="contained"
            onPress={() => router.replace('/(auth)/forgot-password')}
            style={{ marginTop: spacing.xl }}
          >
            {t('auth.requestNewLink')}
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={[styles.scrollContent, { padding: spacing.lg }]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Icon */}
          <View style={[styles.iconContainer, { marginBottom: spacing.lg }]}>
            <MaterialCommunityIcons
              name={isSuccess ? 'check-circle-outline' : 'lock-reset'}
              size={64}
              color={isSuccess ? colors.primary : colors.primary}
            />
          </View>

          <Text
            variant="headlineSmall"
            style={[styles.title, { color: colors.onBackground, marginBottom: spacing.sm }]}
          >
            {isSuccess ? t('auth.passwordResetSuccess') : t('auth.newPasswordTitle')}
          </Text>

          {isSuccess ? (
            <View style={styles.successContainer}>
              <Text
                variant="bodyLarge"
                style={{ color: colors.onSurfaceVariant, textAlign: 'center', marginTop: spacing.md }}
              >
                {t('auth.passwordResetSuccessMessage')}
              </Text>
              <Button
                mode="contained"
                onPress={() => router.replace('/(auth)/sign-in')}
                style={{ marginTop: spacing.xl }}
                contentStyle={styles.buttonContent}
              >
                {t('auth.signIn')}
              </Button>
            </View>
          ) : (
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
              {/* New Password */}
              <Controller
                control={control}
                name="new_password"
                render={({ field: { onChange, onBlur, value } }) => (
                  <View style={{ marginBottom: spacing.sm }}>
                    <TextInput
                      label={t('auth.newPassword')}
                      value={value}
                      onChangeText={onChange}
                      onBlur={onBlur}
                      mode="outlined"
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      error={!!errors.new_password}
                      left={<TextInput.Icon icon="lock-outline" />}
                      right={
                        <TextInput.Icon
                          icon={showPassword ? 'eye-off' : 'eye'}
                          onPress={() => setShowPassword(!showPassword)}
                        />
                      }
                    />
                    <PasswordStrengthIndicator password={watchPassword} />
                  </View>
                )}
              />

              {/* Confirm Password */}
              <Controller
                control={control}
                name="confirm_password"
                render={({ field: { onChange, onBlur, value } }) => (
                  <View style={{ marginBottom: spacing.lg }}>
                    <TextInput
                      label={t('auth.confirmPassword')}
                      value={value}
                      onChangeText={onChange}
                      onBlur={onBlur}
                      mode="outlined"
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      error={!!errors.confirm_password}
                      left={<TextInput.Icon icon="lock-check-outline" />}
                    />
                    {errors.confirm_password && (
                      <HelperText type="error" visible>
                        {t(errors.confirm_password.message ?? '')}
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
                loading={confirmMutation.isPending}
                disabled={confirmMutation.isPending}
                contentStyle={styles.buttonContent}
                style={{ borderRadius: borderRadius.sm }}
              >
                {t('auth.resetPassword')}
              </Button>
            </Surface>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
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
});
