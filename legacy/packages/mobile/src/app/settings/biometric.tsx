/**
 * Settings — Biometric login toggle.
 *
 * NOTE: This screen lets the user enable/disable biometric quick-login. It does
 * NOT fix the latent issue flagged in MOBILE_HOLISTIC_AUDIT_2026_04_27.md (S1)
 * where `saveBiometricCredentials` stores the password without
 * `requireAuthentication`. That fix belongs to Sprint A hardening so the
 * account-deletion flow can land independently. The toggle below is purely
 * additive — it does not introduce or amplify the bug.
 */

import { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import {
  ActivityIndicator,
  Button,
  Dialog,
  HelperText,
  IconButton,
  List,
  Portal,
  Snackbar,
  Surface,
  Switch,
  Text,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { useAuth } from '@core/hooks/use-auth';
import {
  clearBiometricCredentials,
  hasBiometricCredentials,
  isBiometricAvailable,
  saveBiometricCredentials,
} from '@core/security/biometric-login';

function BiometricSettingsContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { user, signIn } = useAuth();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [hardwareReady, setHardwareReady] = useState<boolean | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  // Re-auth dialog (asks for the password to re-enable biometrics)
  const [pwDialog, setPwDialog] = useState(false);
  const [pwInput, setPwInput] = useState('');
  const [pwError, setPwError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    const [hw, has] = await Promise.all([isBiometricAvailable(), hasBiometricCredentials()]);
    setHardwareReady(hw);
    setEnabled(has);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleToggle = (next: boolean) => {
    if (busy) return;
    if (next) setPwDialog(true);
    else void disableBiometric();
  };

  const disableBiometric = useCallback(async () => {
    setBusy(true);
    try {
      await clearBiometricCredentials();
      setEnabled(false);
      setSnackbar(t('settings.biometric.disabled', { defaultValue: 'Biometric disabled' }));
    } finally {
      setBusy(false);
    }
  }, [t]);

  const enableBiometric = useCallback(async () => {
    if (!user?.email || pwInput.length === 0) return;
    setPwError(null);
    setBusy(true);
    try {
      // Re-validate the password against the backend by exercising the same
      // signIn flow used at login. Backend enforces throttling + 2FA gating.
      const result = await signIn(user.email, pwInput);
      if (result.type === 'requires_2fa') {
        setPwError(
          t('settings.biometric.requires2fa', {
            defaultValue: 'Disable 2FA before enabling biometric login.',
          }),
        );
        return;
      }
      await saveBiometricCredentials(user.email, pwInput);
      setEnabled(true);
      setPwDialog(false);
      setPwInput('');
      setSnackbar(t('settings.biometric.enabled', { defaultValue: 'Biometric enabled' }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('errors.serverError');
      setPwError(msg);
    } finally {
      setBusy(false);
    }
  }, [user, pwInput, signIn, t]);

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[
          styles.topBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
        ]}
      >
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {t('settings.biometric.title', { defaultValue: 'Biometric login' })}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.md, gap: spacing.md }}>
        <Surface
          style={[
            styles.card,
            { borderRadius: borderRadius.md, backgroundColor: colors.surface },
          ]}
          elevation={0}
        >
          {loading ? (
            <View style={styles.centered}>
              <ActivityIndicator color={colors.primary} />
            </View>
          ) : !hardwareReady ? (
            <View style={[styles.centered, { padding: spacing.lg }]}>
              <MaterialCommunityIcons
                name="fingerprint-off"
                size={48}
                color={colors.outline}
              />
              <Text
                variant="bodyMedium"
                style={{ color: colors.onSurfaceVariant, marginTop: 12, textAlign: 'center' }}
              >
                {t('settings.biometric.unavailable', {
                  defaultValue:
                    'Biometric authentication is not available or not enrolled on this device.',
                })}
              </Text>
            </View>
          ) : (
            <List.Item
              title={t('settings.biometric.toggle', { defaultValue: 'Use biometric login' })}
              description={t('settings.biometric.description', {
                defaultValue:
                  'Sign in with your fingerprint or face after entering your password once.',
              })}
              left={(props) => <List.Icon {...props} icon="fingerprint" />}
              right={() => (
                <Switch
                  value={enabled}
                  onValueChange={handleToggle}
                  disabled={busy}
                />
              )}
            />
          )}
        </Surface>

        <HelperText type="info" visible padding="none">
          {t('settings.biometric.note', {
            defaultValue:
              'Stored credentials are wiped on sign-out and on toggle off.',
          })}
        </HelperText>
      </ScrollView>

      <Portal>
        <Dialog visible={pwDialog} onDismiss={() => setPwDialog(false)}>
          <Dialog.Title>
            {t('settings.biometric.confirmTitle', { defaultValue: 'Confirm your identity' })}
          </Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium" style={{ marginBottom: 12 }}>
              {t('settings.biometric.confirmBody', {
                defaultValue: 'Enter your account password to enable biometric login.',
              })}
            </Text>
            <TextInput
              value={pwInput}
              onChangeText={(v) => {
                setPwInput(v);
                if (pwError) setPwError(null);
              }}
              secureTextEntry
              mode="outlined"
              label={t('auth.password')}
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="current-password"
            />
            {pwError ? (
              <HelperText type="error" visible padding="none">
                {pwError}
              </HelperText>
            ) : null}
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setPwDialog(false)} disabled={busy}>
              {t('common.cancel')}
            </Button>
            <Button onPress={enableBiometric} loading={busy} disabled={busy || !pwInput}>
              {t('common.confirm')}
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={3000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  card: { paddingVertical: 4, overflow: 'hidden' },
  centered: { padding: 24, alignItems: 'center' },
});

export default function BiometricSettingsScreen() {
  return (
    <AuthGuard>
      <BiometricSettingsContent />
    </AuthGuard>
  );
}
