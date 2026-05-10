/**
 * Two-Factor Authentication Management Screen
 *
 * Displays current 2FA status and allows enable/disable:
 * - Disabled: Enable flow (get secret → verify code → save backup codes)
 * - Enabled: Show status + backup codes remaining + disable option
 *
 * Uses GET /auth/2fa/status, POST /auth/2fa/enable, POST /auth/2fa/verify, POST /auth/2fa/disable
 */

import { useState, useCallback } from 'react';
import { StyleSheet, View, ScrollView } from 'react-native';
import {
  Text,
  Button,
  Surface,
  TextInput,
  HelperText,
  ActivityIndicator,
  Snackbar,
  Chip,
  Divider,
} from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import * as Clipboard from 'expo-clipboard';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { useAppTheme } from '@core/theme';
import {
  twoFactorVerifySchema,
  twoFactorDisableSchema,
  type TwoFactorVerifyInput,
  type TwoFactorDisableInput,
} from '@modules/auth/validations';
import {
  use2FAStatus,
  useEnable2FA,
  useVerify2FASetup,
  useDisable2FA,
} from '@modules/auth/services/auth-hooks';
import type { TwoFactorEnableResponse } from '@core/config/types';

type SetupStep = 'idle' | 'secret' | 'verify' | 'backup_codes';

export default function TwoFactorScreen() {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const { data: status, isLoading } = use2FAStatus();
  const enableMutation = useEnable2FA();
  const verifyMutation = useVerify2FASetup();
  const disableMutation = useDisable2FA();

  const [setupStep, setSetupStep] = useState<SetupStep>('idle');
  const [setupData, setSetupData] = useState<TwoFactorEnableResponse | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [showDisable, setShowDisable] = useState(false);

  // Verify code form
  const verifyForm = useForm<TwoFactorVerifyInput>({
    resolver: zodResolver(twoFactorVerifySchema),
    defaultValues: { code: '' },
  });

  // Disable form
  const disableForm = useForm<TwoFactorDisableInput>({
    resolver: zodResolver(twoFactorDisableSchema),
    defaultValues: { password: '' },
  });

  const handleEnable = useCallback(() => {
    enableMutation.mutate(undefined, {
      onSuccess: (data) => {
        setSetupData(data);
        setSetupStep('secret');
      },
      onError: () => setSnackbar(t('common.errorOccurred')),
    });
  }, [enableMutation, t]);

  const handleVerify = useCallback(
    (data: TwoFactorVerifyInput) => {
      if (!setupData) return;
      verifyMutation.mutate(
        {
          secret: setupData.secret,
          code: data.code,
          backup_codes: setupData.backup_codes,
        },
        {
          onSuccess: () => setSetupStep('backup_codes'),
          onError: () => setSnackbar(t('auth.invalidTwoFactorCode')),
        },
      );
    },
    [setupData, verifyMutation, t],
  );

  const handleDisable = useCallback(
    (data: TwoFactorDisableInput) => {
      disableMutation.mutate(data.password, {
        onSuccess: () => {
          setShowDisable(false);
          setSnackbar(t('profile.twoFactorDisabledSuccess'));
        },
        onError: () => setSnackbar(t('auth.incorrectPassword')),
      });
    },
    [disableMutation, t],
  );

  const copyToClipboard = useCallback(
    async (text: string) => {
      await Clipboard.setStringAsync(text);
      setSnackbar(t('common.copied'));
    },
    [t],
  );

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
      {/* Current Status */}
      <Surface
        style={[styles.card, { padding: spacing.lg, borderRadius: borderRadius.lg, backgroundColor: colors.surface }]}
        elevation={1}
      >
        <View style={styles.statusRow}>
          <MaterialCommunityIcons
            name={status?.two_factor_enabled ? 'shield-check' : 'shield-off-outline'}
            size={40}
            color={status?.two_factor_enabled ? colors.primary : colors.outline}
          />
          <View style={{ marginLeft: 16, flex: 1 }}>
            <Text variant="titleMedium" style={{ color: colors.onSurface, fontWeight: '600' }}>
              {t('profile.twoFactor')}
            </Text>
            <Chip
              compact
              style={{
                marginTop: 4,
                alignSelf: 'flex-start',
                backgroundColor: status?.two_factor_enabled
                  ? colors.primaryContainer
                  : colors.errorContainer,
              }}
              textStyle={{
                color: status?.two_factor_enabled
                  ? colors.onPrimaryContainer
                  : colors.onError,
                fontSize: 12,
              }}
            >
              {status?.two_factor_enabled
                ? t('profile.twoFactorEnabled')
                : t('profile.twoFactorDisabled')}
            </Chip>
          </View>
        </View>

        {status?.two_factor_enabled && status.backup_codes_remaining !== undefined && (
          <Text
            variant="bodySmall"
            style={{ color: colors.onSurfaceVariant, marginTop: 12 }}
          >
            {t('profile.backupCodesRemaining', { count: status.backup_codes_remaining })}
          </Text>
        )}
      </Surface>

      {/* Enable Flow */}
      {!status?.two_factor_enabled && setupStep === 'idle' && (
        <Button
          mode="contained"
          icon="shield-lock"
          onPress={handleEnable}
          loading={enableMutation.isPending}
          style={{ marginTop: spacing.lg }}
          contentStyle={styles.buttonContent}
        >
          {t('profile.twoFactorEnable')}
        </Button>
      )}

      {/* Setup: Secret Display */}
      {setupStep === 'secret' && setupData && (
        <Surface
          style={[styles.card, { padding: spacing.lg, borderRadius: borderRadius.lg, backgroundColor: colors.surface, marginTop: spacing.lg }]}
          elevation={1}
        >
          <Text variant="titleMedium" style={{ fontWeight: '600', marginBottom: 12 }}>
            {t('profile.twoFactorSetupTitle')}
          </Text>
          <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, marginBottom: 16 }}>
            {t('profile.twoFactorSetupDesc')}
          </Text>

          {/* Copyable secret */}
          <Surface style={[styles.secretBox, { backgroundColor: colors.surfaceVariant, borderRadius: 8 }]} elevation={0}>
            <Text variant="titleSmall" style={{ fontFamily: 'monospace', letterSpacing: 2 }}>
              {setupData.secret}
            </Text>
          </Surface>
          <Button
            mode="text"
            icon="content-copy"
            onPress={() => copyToClipboard(setupData.secret)}
            compact
          >
            {t('common.copy')}
          </Button>

          <Divider style={{ marginVertical: 12 }} />

          {/* Verify code */}
          <Controller
            control={verifyForm.control}
            name="code"
            render={({ field: { onChange, onBlur, value } }) => (
              <View style={{ marginBottom: 12 }}>
                <TextInput
                  label={t('profile.twoFactorEnterCode')}
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  keyboardType="number-pad"
                  maxLength={6}
                  error={!!verifyForm.formState.errors.code}
                  left={<TextInput.Icon icon="key" />}
                />
                {verifyForm.formState.errors.code && (
                  <HelperText type="error" visible>
                    {t(verifyForm.formState.errors.code.message ?? '')}
                  </HelperText>
                )}
              </View>
            )}
          />

          <Button
            mode="contained"
            onPress={verifyForm.handleSubmit(handleVerify)}
            loading={verifyMutation.isPending}
            disabled={verifyMutation.isPending}
            contentStyle={styles.buttonContent}
          >
            {t('common.verify')}
          </Button>
        </Surface>
      )}

      {/* Setup: Backup Codes */}
      {setupStep === 'backup_codes' && setupData && (
        <Surface
          style={[styles.card, { padding: spacing.lg, borderRadius: borderRadius.lg, backgroundColor: colors.surface, marginTop: spacing.lg }]}
          elevation={1}
        >
          <MaterialCommunityIcons
            name="check-circle"
            size={48}
            color={colors.primary}
            style={{ alignSelf: 'center', marginBottom: 12 }}
          />
          <Text variant="titleMedium" style={{ fontWeight: '600', textAlign: 'center', marginBottom: 8 }}>
            {t('profile.twoFactorEnabledSuccess')}
          </Text>

          <Text variant="bodyMedium" style={{ color: colors.error, textAlign: 'center', marginBottom: 16, fontWeight: '600' }}>
            {t('profile.twoFactorBackupCodesWarning')}
          </Text>

          <Surface style={[styles.codesBox, { backgroundColor: colors.surfaceVariant, borderRadius: 8 }]} elevation={0}>
            {setupData.backup_codes.map((code, i) => (
              <Text key={i} variant="bodyMedium" style={{ fontFamily: 'monospace', lineHeight: 24 }}>
                {code}
              </Text>
            ))}
          </Surface>

          <Button
            mode="outlined"
            icon="content-copy"
            onPress={() => copyToClipboard(setupData.backup_codes.join('\n'))}
            style={{ marginTop: 12 }}
          >
            {t('profile.copyBackupCodes')}
          </Button>

          <Button
            mode="contained"
            onPress={() => { setSetupStep('idle'); setSetupData(null); }}
            style={{ marginTop: 12 }}
            contentStyle={styles.buttonContent}
          >
            {t('common.done')}
          </Button>
        </Surface>
      )}

      {/* Disable 2FA */}
      {status?.two_factor_enabled && !showDisable && (
        <Button
          mode="outlined"
          icon="shield-off-outline"
          onPress={() => setShowDisable(true)}
          textColor={colors.error}
          style={{ marginTop: spacing.lg, borderColor: colors.error }}
        >
          {t('profile.twoFactorDisable')}
        </Button>
      )}

      {showDisable && (
        <Surface
          style={[styles.card, { padding: spacing.lg, borderRadius: borderRadius.lg, backgroundColor: colors.surface, marginTop: spacing.lg }]}
          elevation={1}
        >
          <Text variant="titleMedium" style={{ fontWeight: '600', marginBottom: 12 }}>
            {t('profile.twoFactorDisableConfirm')}
          </Text>

          <Controller
            control={disableForm.control}
            name="password"
            render={({ field: { onChange, onBlur, value } }) => (
              <View style={{ marginBottom: 16 }}>
                <TextInput
                  label={t('auth.password')}
                  value={value}
                  onChangeText={onChange}
                  onBlur={onBlur}
                  mode="outlined"
                  secureTextEntry
                  error={!!disableForm.formState.errors.password}
                  left={<TextInput.Icon icon="lock-outline" />}
                />
                {disableForm.formState.errors.password && (
                  <HelperText type="error" visible>
                    {t(disableForm.formState.errors.password.message ?? '')}
                  </HelperText>
                )}
              </View>
            )}
          />

          <View style={styles.actions}>
            <Button mode="outlined" onPress={() => setShowDisable(false)} style={{ flex: 1, marginRight: 8 }}>
              {t('common.cancel')}
            </Button>
            <Button
              mode="contained"
              onPress={disableForm.handleSubmit(handleDisable)}
              loading={disableMutation.isPending}
              buttonColor={colors.error}
              style={{ flex: 1 }}
            >
              {t('profile.twoFactorDisable')}
            </Button>
          </View>
        </Surface>
      )}

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  card: { width: '100%' },
  statusRow: { flexDirection: 'row', alignItems: 'center' },
  secretBox: { padding: 16, alignItems: 'center', marginBottom: 8 },
  codesBox: { padding: 16, alignItems: 'center' },
  buttonContent: { paddingVertical: 6 },
  actions: { flexDirection: 'row' },
});
