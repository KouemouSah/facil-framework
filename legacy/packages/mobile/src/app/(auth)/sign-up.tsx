/**
 * Sign Up Screen
 *
 * Two-step registration flow:
 * 1. Email verification — send code via API, user enters 6-digit code
 * 2. Personal data — name, phone, password with Zod validation
 *
 * Uses react-hook-form + Zod aligned with backend RegisterRequest.
 * After registration, AuthProvider auto-redirects (tokens already stored).
 */

import { useState, useCallback, useEffect } from 'react';
import {
  StyleSheet,
  View,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  BackHandler,
} from 'react-native';
import {
  Text,
  TextInput,
  Button,
  Surface,
  ProgressBar,
  HelperText,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Link, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { extractApiError } from '@core/api/errors';
import {
  registerSchema,
  verificationCodeRequestSchema,
  type RegisterInput,
  type VerificationCodeRequestInput,
} from '@modules/auth/validations';
import { useRequestVerificationCode } from '@modules/auth/services/auth-hooks';
import { PasswordStrengthIndicator } from '@modules/auth/components/password-strength-indicator';
import { LegalAcceptanceCard, useLegalVersions } from '@modules/legal';

export default function SignUpScreen() {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const { signUp } = useAuth();
  const router = useRouter();

  // Back button → go to home instead of closing app
  useEffect(() => {
    const handler = BackHandler.addEventListener('hardwareBackPress', () => {
      router.replace('/(tabs)');
      return true;
    });
    return () => handler.remove();
  }, [router]);

  const [step, setStep] = useState<1 | 2>(1);
  const [showPassword, setShowPassword] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [codeSent, setCodeSent] = useState(false);

  // Phase 10/B — Legal acceptance state. Both must be checked before
  // the submit button is enabled. The accepted versions are pulled from
  // /api/v1/legal/versions and sent back in the register payload so the
  // backend can persist `terms_version` / `privacy_version` on the user row.
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const legalVersions = useLegalVersions();

  // Step 1: email verification form
  const emailForm = useForm<VerificationCodeRequestInput>({
    resolver: zodResolver(verificationCodeRequestSchema),
    defaultValues: { email: '' },
  });

  // Step 2: registration form (includes verification code from step 1)
  const registerForm = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: '',
      verification_code: '',
      password: '',
      confirm_password: '',
      first_name: '',
      last_name: '',
      phone: '',
      role: 'citizen',
    },
  });

  const sendCodeMutation = useRequestVerificationCode();

  const handleSendCode = useCallback(async () => {
    const isValid = await emailForm.trigger('email');
    if (!isValid) return;
    if (sendCodeMutation.isPending) return;

    setErrorMessage(null);
    const email = emailForm.getValues('email');

    sendCodeMutation.mutate(email, {
      onSuccess: () => {
        setCodeSent(true);
        // Sync email to registration form
        registerForm.setValue('email', email);
      },
      onError: (error) => {
        const apiError = extractApiError(error);
        setErrorMessage(t(apiError.i18nKey));
      },
    });
  }, [emailForm, registerForm, sendCodeMutation]);

  /**
   * Auto-send verification code when email field loses focus
   * and the email is valid. Avoids spamming during typing.
   */
  const handleEmailBlur = useCallback(async () => {
    const email = emailForm.getValues('email');
    if (!email || codeSent || sendCodeMutation.isPending) return;

    const isValid = await emailForm.trigger('email');
    if (isValid) {
      handleSendCode();
    }
  }, [emailForm, codeSent, sendCodeMutation.isPending, handleSendCode]);

  const handleContinueToStep2 = useCallback(() => {
    const code = registerForm.getValues('verification_code');
    if (!code || code.length < 6) {
      registerForm.setError('verification_code', {
        message: 'auth.invalidVerificationCode',
      });
      return;
    }
    setErrorMessage(null);
    setStep(2);
  }, [registerForm]);

  const handleRegister = useCallback(
    async (data: RegisterInput) => {
      // Defensive guard — submit button is already disabled in this case,
      // but the Zod schema does not enforce these (they're mobile-only and
      // not part of RegisterInput). Block here to avoid sending the
      // payload without versions.
      if (!termsAccepted || !privacyAccepted) {
        setErrorMessage(t('legal.acceptance.required'));
        return;
      }
      if (!legalVersions.data) {
        setErrorMessage(t('common.errorRetry'));
        return;
      }

      setErrorMessage(null);
      setIsRegistering(true);
      try {

        const { confirm_password, ...registerData } = data;
        await signUp({
          ...registerData,
          terms_version_accepted: legalVersions.data.terms_version,
          privacy_version_accepted: legalVersions.data.privacy_version,
        });
        // Navigate to dashboard after successful registration
        router.replace('/(tabs)');
      } catch (error) {
        const apiError = extractApiError(error);
        setErrorMessage(t(apiError.i18nKey));
      } finally {
        setIsRegistering(false);
      }
    },
    [signUp, termsAccepted, privacyAccepted, legalVersions.data, router, t],
  );

  const watchPassword = registerForm.watch('password');
  const stepLabels = [t('auth.verificationCode'), t('auth.personalInfo')];

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={[styles.scrollContent, { padding: spacing.lg }]}
          keyboardShouldPersistTaps="handled"
        >
          {/* Header */}
          <View style={[styles.header, { marginBottom: spacing.lg }]}>
            <Text
              variant="headlineMedium"
              style={[styles.title, { color: colors.onBackground }]}
            >
              {t('auth.createAccountTitle')}
            </Text>
          </View>

          {/* Step indicator */}
          <View style={{ marginBottom: spacing.lg }}>
            <View style={[styles.stepRow, { marginBottom: spacing.sm }]}>
              <Text variant="labelMedium" style={{ color: colors.onSurfaceVariant }}>
                {step === 1 ? `1/2 — ${stepLabels[0]}` : `2/2 — ${stepLabels[1]}`}
              </Text>
            </View>
            <ProgressBar
              progress={step === 1 ? 0.5 : 1}
              color={colors.primary}
              style={{ borderRadius: borderRadius.sm }}
            />
          </View>

          {/* Form Card */}
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
            {step === 1 ? (
              <>
                {/* Email field */}
                <Controller
                  control={emailForm.control}
                  name="email"
                  render={({ field: { onChange, onBlur, value } }) => (
                    <View style={{ marginBottom: spacing.md }}>
                      <TextInput
                        label={t('auth.email')}
                        value={value}
                        onChangeText={(text) => {
                          onChange(text);
                          registerForm.setValue('email', text);
                        }}
                        onBlur={() => {
                          onBlur();
                          handleEmailBlur();
                        }}
                        mode="outlined"
                        keyboardType="email-address"
                        autoCapitalize="none"
                        autoComplete="email"
                        error={!!emailForm.formState.errors.email}
                        left={<TextInput.Icon icon="email-outline" />}
                      />
                      {emailForm.formState.errors.email && (
                        <HelperText type="error" visible>
                          {t(emailForm.formState.errors.email.message ?? 'auth.invalidEmail')}
                        </HelperText>
                      )}
                    </View>
                  )}
                />

                {errorMessage && step === 1 && (
                  <Text
                    variant="bodySmall"
                    style={{ color: colors.error, marginBottom: spacing.sm, textAlign: 'center' }}
                  >
                    {errorMessage}
                  </Text>
                )}

                {/* Send code button */}
                <Button
                  mode="outlined"
                  onPress={handleSendCode}
                  loading={sendCodeMutation.isPending}
                  disabled={sendCodeMutation.isPending}
                  style={{ marginBottom: spacing.md }}
                  icon={codeSent ? 'check' : 'email-fast-outline'}
                >
                  {codeSent ? t('auth.codeSent') : t('auth.sendCode')}
                </Button>

                {/* Verification code input */}
                <Controller
                  control={registerForm.control}
                  name="verification_code"
                  render={({ field: { onChange, onBlur, value } }) => (
                    <View style={{ marginBottom: spacing.lg }}>
                      <TextInput
                        label={t('auth.verificationCode')}
                        value={value}
                        onChangeText={onChange}
                        onBlur={onBlur}
                        mode="outlined"
                        keyboardType="number-pad"
                        maxLength={6}
                        error={!!registerForm.formState.errors.verification_code}
                        left={<TextInput.Icon icon="shield-check-outline" />}
                      />
                      {registerForm.formState.errors.verification_code && (
                        <HelperText type="error" visible>
                          {t(
                            registerForm.formState.errors.verification_code.message ??
                              'auth.invalidVerificationCode',
                          )}
                        </HelperText>
                      )}
                    </View>
                  )}
                />

                <Button
                  mode="contained"
                  onPress={handleContinueToStep2}
                  disabled={!codeSent}
                  contentStyle={styles.buttonContent}
                  style={{ borderRadius: borderRadius.sm }}
                >
                  {t('common.next')}
                </Button>
              </>
            ) : (
              <>
                {/* First Name */}
                <Controller
                  control={registerForm.control}
                  name="first_name"
                  render={({ field: { onChange, onBlur, value } }) => (
                    <View style={{ marginBottom: spacing.md }}>
                      <TextInput
                        label={t('auth.firstName')}
                        value={value}
                        onChangeText={onChange}
                        onBlur={onBlur}
                        mode="outlined"
                        autoCapitalize="words"
                        error={!!registerForm.formState.errors.first_name}
                        left={<TextInput.Icon icon="account-outline" />}
                      />
                      {registerForm.formState.errors.first_name && (
                        <HelperText type="error" visible>
                          {t(registerForm.formState.errors.first_name.message ?? '')}
                        </HelperText>
                      )}
                    </View>
                  )}
                />

                {/* Last Name */}
                <Controller
                  control={registerForm.control}
                  name="last_name"
                  render={({ field: { onChange, onBlur, value } }) => (
                    <View style={{ marginBottom: spacing.md }}>
                      <TextInput
                        label={t('auth.lastName')}
                        value={value}
                        onChangeText={onChange}
                        onBlur={onBlur}
                        mode="outlined"
                        autoCapitalize="words"
                        error={!!registerForm.formState.errors.last_name}
                        left={<TextInput.Icon icon="account-outline" />}
                      />
                      {registerForm.formState.errors.last_name && (
                        <HelperText type="error" visible>
                          {t(registerForm.formState.errors.last_name.message ?? '')}
                        </HelperText>
                      )}
                    </View>
                  )}
                />

                {/* Phone with GE format hint */}
                <Controller
                  control={registerForm.control}
                  name="phone"
                  render={({ field: { onChange, onBlur, value } }) => (
                    <View style={{ marginBottom: spacing.md }}>
                      <TextInput
                        label={t('auth.phone')}
                        value={value}
                        onChangeText={onChange}
                        onBlur={onBlur}
                        mode="outlined"
                        keyboardType="phone-pad"
                        maxLength={9}
                        placeholder="222XXXXXX"
                        error={!!registerForm.formState.errors.phone}
                        left={<TextInput.Icon icon="phone-outline" />}
                      />
                      <HelperText
                        type={registerForm.formState.errors.phone ? 'error' : 'info'}
                        visible
                      >
                        {registerForm.formState.errors.phone
                          ? t(registerForm.formState.errors.phone.message ?? 'auth.invalidPhoneGE')
                          : t('auth.phoneHintGE')}
                      </HelperText>
                    </View>
                  )}
                />

                {/* Password */}
                <Controller
                  control={registerForm.control}
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
                        error={!!registerForm.formState.errors.password}
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
                  control={registerForm.control}
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
                        error={!!registerForm.formState.errors.confirm_password}
                        left={<TextInput.Icon icon="lock-check-outline" />}
                      />
                      {registerForm.formState.errors.confirm_password && (
                        <HelperText type="error" visible>
                          {t(registerForm.formState.errors.confirm_password.message ?? '')}
                        </HelperText>
                      )}
                    </View>
                  )}
                />

                {errorMessage && step === 2 && (
                  <Text
                    variant="bodySmall"
                    style={{ color: colors.error, marginBottom: spacing.md, textAlign: 'center' }}
                  >
                    {errorMessage}
                  </Text>
                )}

                {/* Phase 10/B — Legal acceptance (mobile only, citizen sign-up).
                    Both checkboxes are required before submit. Versions sent
                    in payload come from /api/v1/legal/versions. */}
                <LegalAcceptanceCard
                  termsAccepted={termsAccepted}
                  privacyAccepted={privacyAccepted}
                  onTermsToggle={setTermsAccepted}
                  onPrivacyToggle={setPrivacyAccepted}
                  disabled={isRegistering}
                />

                <View style={styles.stepButtons}>
                  <Button
                    mode="outlined"
                    onPress={() => {
                      setErrorMessage(null);
                      setStep(1);
                    }}
                    style={{ flex: 1, marginRight: spacing.sm }}
                  >
                    {t('common.previous')}
                  </Button>
                  <Button
                    mode="contained"
                    onPress={registerForm.handleSubmit(handleRegister)}
                    loading={isRegistering}
                    disabled={
                      isRegistering ||
                      !termsAccepted ||
                      !privacyAccepted ||
                      !legalVersions.data
                    }
                    contentStyle={styles.buttonContent}
                    style={{ flex: 1, borderRadius: borderRadius.sm }}
                  >
                    {t('auth.signUp')}
                  </Button>
                </View>
              </>
            )}
          </Surface>

          {/* Sign in link */}
          <View style={[styles.footer, { marginTop: spacing.lg }]}>
            <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant }}>
              {t('auth.hasAccount')}{' '}
            </Text>
            <Link href="/(auth)/sign-in">
              <Text variant="bodyMedium" style={{ color: colors.primary, fontWeight: '600' }}>
                {t('auth.signIn')}
              </Text>
            </Link>
          </View>
        </ScrollView>
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
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
  },
  title: {
    fontWeight: '700',
    textAlign: 'center',
  },
  stepRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  formCard: {
    width: '100%',
  },
  buttonContent: {
    paddingVertical: 6,
  },
  stepButtons: {
    flexDirection: 'row',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
