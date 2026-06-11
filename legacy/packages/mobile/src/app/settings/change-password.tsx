/**
 * Change Password Screen — Single-step, aligned with web frontend.
 *
 * Uses POST /users/profile/change-password (same endpoint as web).
 * On success: shows snackbar, then signs out after 2s.
 */

import { useState } from 'react';
import { StyleSheet, View, ScrollView, KeyboardAvoidingView, Platform } from 'react-native';
import { Text, TextInput, Button, HelperText, Snackbar, Divider } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { extractApiError } from '@core/api/errors';
import {
  passwordChangeSchema,
  type PasswordChangeInput,
} from '@modules/auth/validations';
import { useChangePassword } from '@modules/auth/services/auth-hooks';
import { PasswordStrengthIndicator } from '@modules/auth/components/password-strength-indicator';

export default function ChangePasswordScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();
  const { signOut } = useAuth();

  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  const mutation = useChangePassword();

  const form = useForm<PasswordChangeInput>({
    resolver: zodResolver(passwordChangeSchema),
    defaultValues: {
      old_password: '',
      new_password: '',
      confirm_password: '',
    },
  });

  const handleSubmit = (data: PasswordChangeInput) => {
    setErrorMessage(null);
    mutation.mutate(
      { old_password: data.old_password, new_password: data.new_password },
      {
        onSuccess: () => {
          setShowSuccess(true);
          setTimeout(() => signOut(), 2000);
        },
        onError: (error) => {
          setErrorMessage(t(extractApiError(error).i18nKey));
        },
      },
    );
  };

  const watchNewPassword = form.watch('new_password');

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
      >
        <View style={{ backgroundColor: colors.surface }}>
          {/* Current password */}
          <Controller
            control={form.control}
            name="old_password"
            render={({ field: { onChange, onBlur, value } }) => (
              <View style={styles.field}>
                <TextInput
                  label={t('auth.currentPassword')}
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  secureTextEntry={!showPassword}
                  error={!!form.formState.errors.old_password}
                  left={<TextInput.Icon icon="lock-outline" />}
                  right={
                    <TextInput.Icon
                      icon={showPassword ? 'eye-off' : 'eye'}
                      onPress={() => setShowPassword(!showPassword)}
                    />
                  }
                />
                {form.formState.errors.old_password && (
                  <HelperText type="error" visible>
                    {t(form.formState.errors.old_password.message ?? '')}
                  </HelperText>
                )}
              </View>
            )}
          />

          <Divider />

          {/* New password */}
          <Controller
            control={form.control}
            name="new_password"
            render={({ field: { onChange, onBlur, value } }) => (
              <View style={styles.field}>
                <TextInput
                  label={t('auth.newPassword')}
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  secureTextEntry={!showPassword}
                  error={!!form.formState.errors.new_password}
                  left={<TextInput.Icon icon="lock-outline" />}
                />
                {form.formState.errors.new_password && (
                  <HelperText type="error" visible>
                    {t(form.formState.errors.new_password.message ?? '')}
                  </HelperText>
                )}
                <PasswordStrengthIndicator password={watchNewPassword} />
              </View>
            )}
          />

          <Divider />

          {/* Confirm password */}
          <Controller
            control={form.control}
            name="confirm_password"
            render={({ field: { onChange, onBlur, value } }) => (
              <View style={styles.field}>
                <TextInput
                  label={t('auth.confirmPassword')}
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  secureTextEntry={!showPassword}
                  error={!!form.formState.errors.confirm_password}
                  left={<TextInput.Icon icon="lock-check-outline" />}
                />
                {form.formState.errors.confirm_password && (
                  <HelperText type="error" visible>
                    {t(form.formState.errors.confirm_password.message ?? '')}
                  </HelperText>
                )}
              </View>
            )}
          />
        </View>

        {/* Error message */}
        {errorMessage && (
          <Text
            variant="bodySmall"
            style={{ color: colors.error, textAlign: 'center', paddingHorizontal: 16, paddingTop: 12 }}
          >
            {errorMessage}
          </Text>
        )}

        {/* Actions */}
        <View style={styles.actions}>
          <Button
            mode="outlined"
            onPress={() => router.back()}
            style={styles.actionButton}
          >
            {t('common.cancel')}
          </Button>
          <Button
            mode="contained"
            onPress={form.handleSubmit(handleSubmit)}
            loading={mutation.isPending}
            disabled={mutation.isPending}
            style={styles.actionButton}
          >
            {t('profile.changePassword')}
          </Button>
        </View>

        <Text
          variant="bodySmall"
          style={{ color: colors.outline, textAlign: 'center', paddingVertical: spacing.md }}
        >
          {t('profile.passwordChangeLogout')}
        </Text>
      </ScrollView>

      <Snackbar visible={showSuccess} onDismiss={() => setShowSuccess(false)} duration={2000}>
        {t('auth.passwordChanged')}
      </Snackbar>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  field: { paddingHorizontal: 16, paddingVertical: 12 },
  actions: { flexDirection: 'row', gap: 12, padding: 16 },
  actionButton: { flex: 1 },
});
