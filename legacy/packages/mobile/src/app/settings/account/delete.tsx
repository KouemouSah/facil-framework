/**
 * Settings → Account → Delete account (RGPD art. 17 — right to erasure).
 *
 * Calls `DELETE /users/profile` with body `{ password, confirmation: "DELETE" }`.
 * The backend (commit P6.1) verifies the password, soft-deletes the user
 * (`users.deleted_at = NOW()`, email rotated to `<email>.deleted-<uuid>`),
 * revokes all refresh tokens + sessions, and inserts an audit_logs entry.
 * A separate cron purges rows older than 30 days, giving the user a grace
 * period to undo the action.
 *
 * Defense-in-depth on the client side:
 *   - the user must enter their current password
 *   - they must type the literal string "DELETE" (case-sensitive, like backend)
 *   - a final native Alert asks for confirmation before the request fires
 */

import { useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import {
  Button,
  HelperText,
  IconButton,
  Snackbar,
  Surface,
  Text,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import apiClient from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { useAuth } from '@core/hooks/use-auth';

const CONFIRM_LITERAL = 'DELETE';

function AccountDeleteContent() {
  const router = useRouter();
  const { t } = useTranslation();
  const { signOut } = useAuth();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValid =
    password.length > 0 && confirmation === CONFIRM_LITERAL && !busy;

  const performDelete = async () => {
    setBusy(true);
    setError(null);
    try {
      await apiClient.delete(API_ENDPOINTS.users.deleteAccount, {
        data: { password, confirmation: CONFIRM_LITERAL },
      });
      // Best-effort logout (also clears tokens locally) then redirect.
      await signOut();
      router.replace('/onboarding' as never);
    } catch (e: unknown) {
      const status = (e as { response?: { status?: number } })?.response?.status;
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (status === 400) {
        setError(
          detail ?? t('settings.deleteAccount.errors.wrongPassword', {
            defaultValue: 'Incorrect password.',
          }),
        );
      } else if (status === 409) {
        setError(t('settings.deleteAccount.errors.alreadyDeleted', {
          defaultValue: 'Account already scheduled for deletion.',
        }));
      } else {
        setError(detail ?? t('errors.serverError'));
      }
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = () => {
    if (!isValid) return;
    Alert.alert(
      t('settings.deleteAccount.confirmTitle', {
        defaultValue: 'Delete your account?',
      }),
      t('settings.deleteAccount.confirmBody', {
        defaultValue:
          'Your account will be soft-deleted now. You have 30 days to undo before all data is permanently erased.',
      }),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('settings.deleteAccount.confirmAction', { defaultValue: 'Delete' }),
          style: 'destructive',
          onPress: () => {
            void performDelete();
          },
        },
      ],
    );
  };

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
          {t('settings.deleteAccount.title', { defaultValue: 'Delete account' })}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={[styles.scroll, { padding: spacing.md }]}
        keyboardShouldPersistTaps="handled"
      >
        <Surface
          style={[
            styles.warningCard,
            {
              padding: spacing.lg,
              borderRadius: borderRadius.md,
              backgroundColor: colors.errorContainer,
              gap: spacing.sm,
            },
          ]}
          elevation={0}
        >
          <View style={styles.warningHeader}>
            <MaterialCommunityIcons
              name="alert-circle-outline"
              size={28}
              color={colors.error}
            />
            <Text
              variant="titleMedium"
              style={{ color: colors.error, fontWeight: '700' }}
            >
              {t('settings.deleteAccount.warning', {
                defaultValue: 'This action cannot be undone after 30 days.',
              })}
            </Text>
          </View>
          <Text style={{ color: colors.error }}>
            {'• '}
            {t('settings.deleteAccount.bullet1', {
              defaultValue: 'Your active sessions will be signed out immediately.',
            })}
          </Text>
          <Text style={{ color: colors.error }}>
            {'• '}
            {t('settings.deleteAccount.bullet2', {
              defaultValue:
                'Your fiscal records remain in the audit ledger as required by law.',
            })}
          </Text>
          <Text style={{ color: colors.error }}>
            {'• '}
            {t('settings.deleteAccount.bullet3', {
              defaultValue:
                'Personal data is purged after 30 days unless you contact support.',
            })}
          </Text>
        </Surface>

        <Surface
          style={[
            styles.formCard,
            {
              padding: spacing.lg,
              marginTop: spacing.md,
              borderRadius: borderRadius.md,
              backgroundColor: colors.surface,
              gap: spacing.md,
            },
          ]}
          elevation={0}
        >
          <TextInput
            label={t('auth.password')}
            value={password}
            onChangeText={(v) => {
              setPassword(v);
              if (error) setError(null);
            }}
            secureTextEntry
            mode="outlined"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="current-password"
            left={<TextInput.Icon icon="lock-outline" />}
          />

          <View>
            <TextInput
              label={t('settings.deleteAccount.typeDelete', {
                defaultValue: 'Type DELETE to confirm',
              })}
              value={confirmation}
              onChangeText={(v) => {
                setConfirmation(v);
                if (error) setError(null);
              }}
              autoCapitalize="characters"
              autoCorrect={false}
              mode="outlined"
            />
            <HelperText
              type={
                confirmation && confirmation !== CONFIRM_LITERAL ? 'error' : 'info'
              }
              visible={!!confirmation && confirmation !== CONFIRM_LITERAL}
            >
              {t('settings.deleteAccount.typeDeleteHint', {
                defaultValue: 'Must be the exact uppercase word DELETE.',
              })}
            </HelperText>
          </View>

          <Button
            mode="contained"
            buttonColor={colors.error}
            textColor={colors.onError}
            icon="trash-can-outline"
            loading={busy}
            disabled={!isValid}
            onPress={handleDelete}
            contentStyle={{ paddingVertical: 6 }}
          >
            {t('settings.deleteAccount.cta', {
              defaultValue: 'Permanently delete my account',
            })}
          </Button>
        </Surface>
      </ScrollView>

      <Snackbar visible={!!error} onDismiss={() => setError(null)} duration={5000}>
        {error ?? ''}
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
  scroll: { flexGrow: 1 },
  warningCard: {},
  warningHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  formCard: {},
});

export default function AccountDeleteScreen() {
  return (
    <AuthGuard>
      <AccountDeleteContent />
    </AuthGuard>
  );
}
