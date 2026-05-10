/**
 * 2FA Verification Screen - Facil Inspeccion
 *
 * 6-digit TOTP code input after successful email/password login.
 * Auto-submits when all 6 digits are entered.
 * 5-minute countdown timer for code validity.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  TextInput as RNTextInput,
  View,
} from 'react-native';
import { Button, HelperText, IconButton, Text } from 'react-native-paper';
import { router, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

import { useAuth } from '@core/hooks/use-auth';
import { useAppTheme } from '@core/theme';
import { extractApiError } from '@core/api/errors';

// --- Zod Schema ---
const twoFactorSchema = z.object({
  code: z
    .string()
    .length(6, 'Code must be exactly 6 digits')
    .regex(/^\d{6}$/, 'Code must contain only digits'),
});

type TwoFactorFormData = z.infer<typeof twoFactorSchema>;

// --- Constants ---
const CODE_LENGTH = 6;
const CODE_VALIDITY_SECONDS = 5 * 60; // 5 minutes

export default function Verify2FAScreen() {
  const { t } = useTranslation();
  const { verify2fa } = useAuth();
  const theme = useAppTheme();
  const { colors } = theme;

  const { temp_token, email } = useLocalSearchParams<{
    temp_token: string;
    email: string;
  }>();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [remainingSeconds, setRemainingSeconds] = useState(CODE_VALIDITY_SECONDS);
  const [isExpired, setIsExpired] = useState(false);

  const inputRefs = useRef<(RNTextInput | null)[]>([]);
  const [digits, setDigits] = useState<string[]>(Array(CODE_LENGTH).fill(''));
  const hasAutoSubmitted = useRef(false);

  const {
    control,
    handleSubmit,
    setValue,
    watch,
    formState: { isValid },
  } = useForm<TwoFactorFormData>({
    resolver: zodResolver(twoFactorSchema),
    defaultValues: { code: '' },
    mode: 'onChange',
  });

  const codeValue = watch('code');

  // --- Countdown timer ---
  useEffect(() => {
    const interval = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setIsExpired(true);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // --- Format remaining time as MM:SS ---
  const formatTime = useCallback((seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }, []);

  // --- Sync individual digits to form code value ---
  const updateCode = useCallback(
    (newDigits: string[]) => {
      setDigits(newDigits);
      const code = newDigits.join('');
      setValue('code', code, { shouldValidate: true });
    },
    [setValue],
  );

  // --- Handle digit input ---
  const handleDigitChange = useCallback(
    (index: number, value: string) => {
      // Only accept single digit
      const digit = value.replace(/\D/g, '').slice(-1);
      const newDigits = [...digits];
      newDigits[index] = digit;
      updateCode(newDigits);

      // Auto-advance to next input
      if (digit && index < CODE_LENGTH - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [digits, updateCode],
  );

  // --- Handle backspace ---
  const handleKeyPress = useCallback(
    (index: number, key: string) => {
      if (key === 'Backspace' && !digits[index] && index > 0) {
        // Move to previous input and clear it
        const newDigits = [...digits];
        newDigits[index - 1] = '';
        updateCode(newDigits);
        inputRefs.current[index - 1]?.focus();
      }
    },
    [digits, updateCode],
  );

  // --- Auto-submit when 6 digits entered ---
  useEffect(() => {
    if (
      codeValue.length === CODE_LENGTH &&
      /^\d{6}$/.test(codeValue) &&
      !isSubmitting &&
      !isExpired &&
      !hasAutoSubmitted.current
    ) {
      hasAutoSubmitted.current = true;
      Keyboard.dismiss();
      handleSubmit(onSubmit)();
    }
  }, [codeValue, isSubmitting, isExpired]);

  // --- Submit handler ---
  const onSubmit = useCallback(
    async (data: TwoFactorFormData) => {
      if (!temp_token) {
        setError('Missing authentication token');
        return;
      }

      if (isExpired) {
        setError(t('auth.codeExpired'));
        return;
      }

      setError('');
      setIsSubmitting(true);

      try {
        await verify2fa(temp_token, data.code);
        router.replace('/(tabs)');
      } catch (err) {
        const apiError = extractApiError(err);
        // Check for specific error codes
        if (apiError.status === 401 || apiError.code === 'INVALID_2FA_CODE') {
          setError(t('auth.invalidCode'));
        } else if (apiError.status === 410 || apiError.code === 'TOKEN_EXPIRED') {
          setError(t('auth.codeExpired'));
          setIsExpired(true);
        } else {
          setError(apiError.message);
        }
        // Reset auto-submit guard so user can retry
        hasAutoSubmitted.current = false;
      } finally {
        setIsSubmitting(false);
      }
    },
    [temp_token, isExpired, verify2fa, t],
  );

  // --- Clear and retry ---
  const handleClear = useCallback(() => {
    setDigits(Array(CODE_LENGTH).fill(''));
    setValue('code', '', { shouldValidate: true });
    setError('');
    hasAutoSubmitted.current = false;
    inputRefs.current[0]?.focus();
  }, [setValue]);

  // --- Go back to sign-in ---
  const handleBack = useCallback(() => {
    router.back();
  }, []);

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <View style={styles.content}>
        {/* Back button */}
        <View style={styles.backRow}>
          <IconButton
            icon="arrow-left"
            size={24}
            onPress={handleBack}
            disabled={isSubmitting}
          />
        </View>

        {/* Header */}
        <View style={styles.header}>
          <View style={[styles.iconContainer, { backgroundColor: colors.primary }]}>
            <Text style={styles.iconText}>2FA</Text>
          </View>
          <Text variant="headlineMedium" style={[styles.title, { color: colors.primary }]}>
            {t('auth.twoFactorTitle')}
          </Text>
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, textAlign: 'center' }}>
            {t('auth.twoFactorSubtitle')}
          </Text>
          {email ? (
            <Text
              variant="bodySmall"
              style={{ color: colors.onSurfaceVariant, marginTop: 4 }}
            >
              {email}
            </Text>
          ) : null}
        </View>

        {/* Code input boxes */}
        <View style={styles.form}>
          <Text variant="labelLarge" style={{ color: colors.onSurface, marginBottom: 8 }}>
            {t('auth.enterCode')}
          </Text>

          <Controller
            control={control}
            name="code"
            render={() => (
              <View style={styles.codeRow}>
                {Array.from({ length: CODE_LENGTH }).map((_, index) => (
                  <RNTextInput
                    key={index}
                    ref={(ref) => {
                      inputRefs.current[index] = ref;
                    }}
                    style={[
                      styles.codeBox,
                      {
                        borderColor: digits[index]
                          ? colors.primary
                          : error
                            ? colors.error
                            : colors.outline,
                        backgroundColor: colors.surface,
                        color: colors.onSurface,
                      },
                    ]}
                    value={digits[index]}
                    onChangeText={(value) => handleDigitChange(index, value)}
                    onKeyPress={({ nativeEvent }) => handleKeyPress(index, nativeEvent.key)}
                    keyboardType="number-pad"
                    maxLength={1}
                    textContentType="oneTimeCode"
                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                    selectTextOnFocus
                    editable={!isSubmitting && !isExpired}
                    autoFocus={index === 0}
                  />
                ))}
              </View>
            )}
          />

          {/* Timer */}
          <View style={styles.timerRow}>
            <Text
              variant="bodySmall"
              style={{
                color: isExpired
                  ? colors.error
                  : remainingSeconds <= 60
                    ? colors.error
                    : colors.onSurfaceVariant,
              }}
            >
              {isExpired
                ? t('auth.codeExpired')
                : `${t('auth.codeExpires')} ${formatTime(remainingSeconds)}`}
            </Text>
          </View>

          {/* Error message */}
          {error ? (
            <HelperText type="error" visible={!!error}>
              {error}
            </HelperText>
          ) : null}

          {/* Verify button */}
          <Button
            mode="contained"
            onPress={handleSubmit(onSubmit)}
            loading={isSubmitting}
            disabled={isSubmitting || !isValid || isExpired}
            style={styles.button}
          >
            {isSubmitting ? t('auth.verifying') : t('auth.verify')}
          </Button>

          {/* Clear / Resend row */}
          <View style={styles.actionsRow}>
            {error || codeValue.length > 0 ? (
              <Button
                mode="text"
                onPress={handleClear}
                disabled={isSubmitting}
                compact
              >
                {t('common.retry')}
              </Button>
            ) : null}

            {isExpired ? (
              <Button
                mode="text"
                onPress={handleBack}
                compact
              >
                {t('auth.resendCode')}
              </Button>
            ) : null}
          </View>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { flex: 1, justifyContent: 'center', padding: 24 },
  backRow: { position: 'absolute', top: 48, left: 8 },
  header: { alignItems: 'center', marginBottom: 40 },
  iconContainer: {
    width: 72,
    height: 72,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  iconText: { color: '#FFFFFF', fontSize: 22, fontWeight: '700' },
  title: { fontWeight: '700', marginBottom: 4 },
  form: { gap: 12 },
  codeRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
  },
  codeBox: {
    width: 48,
    height: 56,
    borderWidth: 2,
    borderRadius: 12,
    textAlign: 'center',
    fontSize: 24,
    fontWeight: '700',
  },
  timerRow: {
    alignItems: 'center',
    marginTop: 4,
  },
  button: { marginTop: 8, paddingVertical: 4 },
  actionsRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 16,
    marginTop: 8,
  },
});
