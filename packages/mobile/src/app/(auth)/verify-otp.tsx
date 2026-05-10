/**
 * OTP Verification Screen
 *
 * 6-digit TOTP code input for two-factor authentication.
 * Shown after sign-in when 2FA is enabled on the account.
 * Receives tempToken via route params and calls verify2FA on submit.
 */

import { useState, useRef } from 'react';
import {
  StyleSheet,
  View,
  TextInput as RNTextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { Text, Button, Surface } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { extractApiError } from '@core/api/errors';

const OTP_LENGTH = 6;

export default function VerifyOtpScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const { verify2FA } = useAuth();
  const { tempToken } = useLocalSearchParams<{ tempToken: string }>();

  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRefs = useRef<(RNTextInput | null)[]>([]);

  const handleChange = (value: string, index: number) => {
    if (value.length > 1) {
      // Handle paste — distribute characters across inputs
      const chars = value.slice(0, OTP_LENGTH).split('');
      const newOtp = [...otp];
      chars.forEach((char, i) => {
        if (index + i < OTP_LENGTH) {
          newOtp[index + i] = char;
        }
      });
      setOtp(newOtp);
      const focusIndex = Math.min(index + chars.length, OTP_LENGTH - 1);
      inputRefs.current[focusIndex]?.focus();
      return;
    }

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    // Auto-advance to next input
    if (value && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyPress = (key: string, index: number) => {
    if (key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const otpValue = otp.join('');

  const handleVerify = async () => {
    if (!tempToken) {
      setErrorMessage('Missing authentication token. Please sign in again.');
      return;
    }
    setErrorMessage(null);
    setIsSubmitting(true);
    try {
      await verify2FA(tempToken, otpValue);
      // Navigate to dashboard after successful 2FA
      router.replace('/(tabs)');
    } catch (error) {
      const apiError = extractApiError(error);
      setErrorMessage(t(apiError.i18nKey));
    } finally {
      setIsSubmitting(false);
    }
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
              name="shield-lock-outline"
              size={64}
              color={colors.primary}
            />
          </View>

          {/* Title */}
          <Text
            variant="headlineSmall"
            style={[styles.title, { color: colors.onBackground, marginBottom: spacing.sm }]}
          >
            {t('auth.twoFactorTitle')}
          </Text>
          <Text
            variant="bodyMedium"
            style={[styles.subtitle, { color: colors.onSurfaceVariant, marginBottom: spacing.xl }]}
          >
            {t('auth.twoFactorDescription')}
          </Text>

          {/* OTP inputs */}
          <Surface
            style={[
              styles.otpCard,
              {
                padding: spacing.lg,
                borderRadius: borderRadius.lg,
                backgroundColor: colors.surface,
              },
            ]}
            elevation={1}
          >
            <View style={[styles.otpRow, { gap: spacing.sm }]}>
              {otp.map((digit, index) => (
                <RNTextInput
                  key={index}
                  ref={(ref) => {
                    inputRefs.current[index] = ref;
                  }}
                  value={digit}
                  onChangeText={(value) => handleChange(value, index)}
                  onKeyPress={({ nativeEvent }) =>
                    handleKeyPress(nativeEvent.key, index)
                  }
                  keyboardType="number-pad"
                  maxLength={index === 0 ? OTP_LENGTH : 1}
                  style={[
                    styles.otpInput,
                    {
                      borderColor: digit
                        ? colors.primary
                        : colors.outlineVariant,
                      color: colors.onSurface,
                      backgroundColor: colors.surface,
                      borderRadius: borderRadius.sm,
                    },
                  ]}
                  textAlign="center"
                  selectTextOnFocus
                />
              ))}
            </View>

            {errorMessage && (
              <Text
                variant="bodySmall"
                style={{ color: colors.error, marginTop: spacing.md, textAlign: 'center' }}
              >
                {errorMessage}
              </Text>
            )}

            <Button
              mode="contained"
              onPress={handleVerify}
              loading={isSubmitting}
              disabled={isSubmitting || otpValue.length < OTP_LENGTH}
              contentStyle={styles.buttonContent}
              style={{ borderRadius: borderRadius.sm, marginTop: spacing.lg }}
            >
              {t('common.confirm')}
            </Button>
          </Surface>
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
  subtitle: {
    textAlign: 'center',
  },
  otpCard: {
    width: '100%',
    alignItems: 'center',
  },
  otpRow: {
    flexDirection: 'row',
    justifyContent: 'center',
  },
  otpInput: {
    width: 44,
    height: 52,
    borderWidth: 2,
    fontSize: 22,
    fontWeight: '700',
  },
  buttonContent: {
    paddingVertical: 6,
  },
});
