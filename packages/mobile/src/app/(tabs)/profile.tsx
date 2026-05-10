/**
 * Profile Tab — Android 14+ native style
 *
 * Flat list design with dividers (no elevated cards).
 * Continuous vertical flow like Android Settings.
 */

import { useState, useCallback, useEffect } from 'react';
import { StyleSheet, View, ScrollView, Alert , Switch } from 'react-native';
import {
  Text,
  Button,
  Divider,
  List,
  Snackbar,
  ActivityIndicator,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import { AuthGuard } from '@core/auth/auth-guard';
import { useAppLock } from '@core/security/app-lock';
import { useScreenProtection } from '@core/security/use-screen-protection';
import type { SupportedLanguage, UserUpdateRequest } from '@core/config/types';

import { useProfile, useUpdateProfile, useUploadAvatar, useDeleteAvatar } from '@modules/profile';
import { ProfileHeader } from '@modules/profile/components/profile-header';
import { ProfileEditForm } from '@modules/profile/components/profile-edit-form';
import { AvatarPicker } from '@modules/profile/components/avatar-picker';
import { NotificationSettings } from '@modules/profile/components/notification-settings';
import { LanguagePicker } from '@modules/profile/components/language-picker';
import type { ProfileUpdateInput } from '@modules/profile/validations';

/** Format phone for display: handles both prefixed (+240222...) and raw (222...) numbers */
function formatPhoneDisplay(phone: string): string {
  const digits = phone.replace(/[^0-9]/g, '');
  if (digits.length === 12 && digits.startsWith('240')) {
    const local = digits.slice(3);
    return `+240 ${local.slice(0, 3)} ${local.slice(3, 6)} ${local.slice(6)}`;
  }
  if (digits.length === 9) {
    return `+240 ${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
  }
  return phone;
}

const LANGUAGE_LABELS: Record<string, string> = {
  es: 'Español',
  fr: 'Français',
  en: 'English',
};

function AppLockToggle() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { isAppLockEnabled, isBiometricAvailable, setAppLockEnabled } = useAppLock();

  if (!isBiometricAvailable) return null;

  return (
    <>
      <Divider style={{ marginLeft: 56 }} />
      <List.Item
        title={t('settings.appLock')}
        description={t('settings.appLockDesc')}
        left={(props) => <List.Icon {...props} icon="fingerprint" />}
        right={() => (
          <Switch
            value={isAppLockEnabled}
            onValueChange={setAppLockEnabled}
            trackColor={{ false: '#ccc', true: colors.primary + '80' }}
            thumbColor={isAppLockEnabled ? colors.primary : '#f4f4f4'}
          />
        )}
      />
    </>
  );
}

function ProfileScreenContent() {
  useScreenProtection();
  const { t, i18n } = useTranslation();
  const { colors } = useAppTheme();
  const { user, signOut } = useAuth();
  const router = useRouter();

  // Remote profile data
  const { data: profile } = useProfile(!!user);
  const updateMutation = useUpdateProfile();
  const uploadAvatarMutation = useUploadAvatar();
  const deleteAvatarMutation = useDeleteAvatar();

  const displayUser = profile ?? user;

  // Sync i18n language with user's preferred_language from backend
  useEffect(() => {
    if (displayUser?.preferred_language && displayUser.preferred_language !== i18n.language) {
      i18n.changeLanguage(displayUser.preferred_language);
    }
  }, [displayUser?.preferred_language, i18n]);

  // UI state
  const [isEditing, setIsEditing] = useState(false);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [showLanguagePicker, setShowLanguagePicker] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState<string | null>(null);

  const [notifPrefs, setNotifPrefs] = useState({
    email_notifications: displayUser?.email_notifications ?? true,
    push_notifications: displayUser?.push_notifications ?? true,
    sms_notifications: displayUser?.sms_notifications ?? false,
  });

  const handleSignOut = useCallback(() => {
    Alert.alert(
      t('auth.signOutTitle'),
      t('auth.signOutMessage'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        { text: t('auth.signOut'), style: 'destructive', onPress: () => signOut() },
      ],
    );
  }, [t, signOut]);

  const handleSaveProfile = useCallback(
    (data: ProfileUpdateInput) => {
      const updateData: UserUpdateRequest = {};
      if (data.first_name) updateData.first_name = data.first_name;
      if (data.last_name) updateData.last_name = data.last_name;
      if (data.phone_number) updateData.phone_number = data.phone_number;
      if (data.address !== undefined) updateData.address = data.address || undefined;
      if (data.city !== undefined) updateData.city = data.city || undefined;

      updateMutation.mutate(updateData, {
        onSuccess: () => {
          setIsEditing(false);
          setSnackbarMessage(t('profile.profileUpdated'));
        },
        onError: () => setSnackbarMessage(t('common.errorOccurred')),
      });
    },
    [updateMutation, t],
  );

  const handleAvatarSelected = useCallback(
    (uri: string) => {
      uploadAvatarMutation.mutate(
        { uri },
        {
          onSuccess: () => setSnackbarMessage(t('profile.avatarUpdated')),
          onError: () => setSnackbarMessage(t('common.errorOccurred')),
        },
      );
    },
    [uploadAvatarMutation, t],
  );

  const handleAvatarRemove = useCallback(() => {
    deleteAvatarMutation.mutate(undefined, {
      onSuccess: () => setSnackbarMessage(t('profile.avatarRemoved')),
      onError: () => setSnackbarMessage(t('common.errorOccurred')),
    });
  }, [deleteAvatarMutation, t]);

  const handleNotifUpdate = useCallback((field: string, value: boolean) => {
    setNotifPrefs((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleLanguageChanged = useCallback((_lang: SupportedLanguage) => {
    setSnackbarMessage(null);
  }, []);

  if (!displayUser) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
      <ScrollView>
        {/* ── Header: avatar + name + role ── */}
        <ProfileHeader
          user={displayUser}
          onAvatarPress={() => setShowAvatarPicker(true)}
          isUploading={uploadAvatarMutation.isPending}
        />

        <Divider />

        {/* ── Personal Info ── */}
        {isEditing ? (
          <View style={{ backgroundColor: colors.surface }}>
            <ProfileEditForm
              user={displayUser}
              onSave={handleSaveProfile}
              onCancel={() => setIsEditing(false)}
              isSaving={updateMutation.isPending}
            />
          </View>
        ) : (
          <View style={{ backgroundColor: colors.surface }}>
            <View style={styles.sectionHeader}>
              <List.Subheader style={{ color: colors.primary, flex: 1 }}>
                {t('profile.personalInfo')}
              </List.Subheader>
              <Button
                mode="text"
                compact
                icon="pencil"
                onPress={() => setIsEditing(true)}
                style={{ marginRight: 8 }}
              >
                {t('common.edit')}
              </Button>
            </View>

            <List.Item
              title={t('auth.firstName')}
              description={displayUser.first_name}
              left={(props) => <List.Icon {...props} icon="account-outline" />}
            />
            <Divider style={styles.insetDivider} />
            <List.Item
              title={t('auth.lastName')}
              description={displayUser.last_name}
              left={(props) => <List.Icon {...props} icon="account-outline" />}
            />
            <Divider style={styles.insetDivider} />
            <List.Item
              title={t('auth.email')}
              description={displayUser.email}
              left={(props) => <List.Icon {...props} icon="email-outline" />}
            />
            {displayUser.phone_number && (
              <>
                <Divider style={styles.insetDivider} />
                <List.Item
                  title={t('auth.phone')}
                  description={formatPhoneDisplay(displayUser.phone_number)}
                  left={(props) => <List.Icon {...props} icon="phone-outline" />}
                />
              </>
            )}
            {displayUser.address && (
              <>
                <Divider style={styles.insetDivider} />
                <List.Item
                  title={t('profile.address')}
                  description={displayUser.address}
                  left={(props) => <List.Icon {...props} icon="map-marker-outline" />}
                />
              </>
            )}
            {displayUser.city && (
              <>
                <Divider style={styles.insetDivider} />
                <List.Item
                  title={t('profile.city')}
                  description={displayUser.city}
                  left={(props) => <List.Icon {...props} icon="city-variant-outline" />}
                />
              </>
            )}
          </View>
        )}

        <Divider />

        {/* ── Activity ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Item
            title={t('payments.list.title')}
            left={(props) => <List.Icon {...props} icon="cash-multiple" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/(tabs)/payments' as never)}
          />
        </View>

        <Divider />

        {/* ── Preferences ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.preferences')}
          </List.Subheader>
          <List.Item
            title={t('profile.languageTitle')}
            description={LANGUAGE_LABELS[displayUser.preferred_language] ?? 'Español'}
            left={(props) => <List.Icon {...props} icon="translate" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => setShowLanguagePicker(true)}
          />
        </View>

        <Divider />

        {/* ── Notifications ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <NotificationSettings
            emailNotifications={notifPrefs.email_notifications}
            pushNotifications={notifPrefs.push_notifications}
            smsNotifications={notifPrefs.sms_notifications}
            onUpdate={handleNotifUpdate}
          />
        </View>

        <Divider />

        {/* ── Security ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.security')}
          </List.Subheader>
          <List.Item
            title={t('profile.changePassword')}
            left={(props) => <List.Icon {...props} icon="lock-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/change-password')}
          />
          <Divider style={styles.insetDivider} />
          <List.Item
            title={t('profile.twoFactor')}
            description={
              displayUser.two_factor_enabled
                ? t('profile.twoFactorEnabled')
                : t('profile.twoFactorDisabled')
            }
            left={(props) => <List.Icon {...props} icon="shield-lock-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/two-factor')}
          />
          <Divider style={styles.insetDivider} />
          <List.Item
            title={t('profile.sessions')}
            left={(props) => <List.Icon {...props} icon="devices" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/sessions')}
          />
          <Divider style={styles.insetDivider} />
          <List.Item
            title={t('settings.biometric.title', { defaultValue: 'Biometric login' })}
            left={(props) => <List.Icon {...props} icon="fingerprint" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/biometric' as never)}
          />
          <Divider style={styles.insetDivider} />
          <List.Item
            title={t('settings.notifications.title', {
              defaultValue: t('profile.notifications'),
            })}
            left={(props) => <List.Icon {...props} icon="bell-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/notifications' as never)}
          />
          <AppLockToggle />
        </View>

        <Divider />

        {/* ── My data — RGPD art. 20 export ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.myData', { defaultValue: 'My data' })}
          </List.Subheader>
          <List.Item
            title={t('settings.exportData.title', {
              defaultValue: 'Export my data',
            })}
            description={t('settings.exportData.subtitleShort', {
              defaultValue: 'JSON download — RGPD art. 20',
            })}
            left={(props) => <List.Icon {...props} icon="download-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/account/export' as never)}
          />
        </View>

        <Divider />

        {/* ── Legal — Phase 10/B Privacy Policy + Terms of Service + Cookies ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.primary }}>
            {t('settings.legal', { defaultValue: 'Legal' })}
          </List.Subheader>
          <List.Item
            title={t('legal.privacy.title', { defaultValue: 'Privacy Policy' })}
            left={(props) => <List.Icon {...props} icon="shield-lock-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/legal/privacy' as never)}
          />
          <List.Item
            title={t('legal.terms.title', { defaultValue: 'Terms of Service' })}
            left={(props) => <List.Icon {...props} icon="file-document-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/legal/terms' as never)}
          />
          <List.Item
            title={t('legal.cookies.title', { defaultValue: 'Cookie Policy' })}
            left={(props) => <List.Icon {...props} icon="cookie-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/legal/cookies' as never)}
          />
          <List.Item
            title={t('settings.about.title', { defaultValue: 'About Facil' })}
            description={t('settings.about.subtitle', { defaultValue: 'Version, copyright, contact' })}
            left={(props) => <List.Icon {...props} icon="information-outline" />}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            onPress={() => router.push('/settings/about' as never)}
          />
        </View>

        <Divider />

        {/* ── Danger zone — RGPD account deletion ── */}
        <View style={{ backgroundColor: colors.surface }}>
          <List.Subheader style={{ color: colors.error }}>
            {t('settings.dangerZone', { defaultValue: 'Danger zone' })}
          </List.Subheader>
          <List.Item
            title={t('settings.deleteAccount.title', {
              defaultValue: 'Delete my account',
            })}
            left={(props) => (
              <List.Icon {...props} icon="trash-can-outline" color={colors.error} />
            )}
            right={(props) => <List.Icon {...props} icon="chevron-right" />}
            titleStyle={{ color: colors.error }}
            onPress={() => router.push('/settings/account/delete' as never)}
          />
        </View>

        <Divider />

        {/* ── Sign Out ── */}
        <View style={{ backgroundColor: colors.surface, padding: 16 }}>
          <Button
            mode="text"
            icon="logout"
            onPress={handleSignOut}
            textColor={colors.error}
            contentStyle={{ justifyContent: 'flex-start' }}
          >
            {t('auth.signOut')}
          </Button>
        </View>

        {/* ── Version ── */}
        <Text
          variant="bodySmall"
          style={{ textAlign: 'center', color: colors.outline, paddingVertical: 16 }}
        >
          Facil v1.0.0
        </Text>
      </ScrollView>

      {/* ── Modals ── */}
      <AvatarPicker
        visible={showAvatarPicker}
        onDismiss={() => setShowAvatarPicker(false)}
        onImageSelected={handleAvatarSelected}
        onRemove={handleAvatarRemove}
        hasAvatar={!!displayUser.avatar_url}
      />
      <LanguagePicker
        visible={showLanguagePicker}
        onDismiss={() => setShowLanguagePicker(false)}
        currentLanguage={displayUser.preferred_language}
        onLanguageChanged={handleLanguageChanged}
      />

      <Snackbar
        visible={!!snackbarMessage}
        onDismiss={() => setSnackbarMessage(null)}
        duration={3000}
      >
        {snackbarMessage ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  insetDivider: {
    marginLeft: 56,
  },
});

export default function ProfileScreen() {
  return (
    <AuthGuard>
      <ProfileScreenContent />
    </AuthGuard>
  );
}
