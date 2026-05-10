/**
 * App Lock — Biometric lock screen on resume from background
 *
 * Behavior:
 * - Only active when user is authenticated
 * - When app goes to background, records timestamp
 * - On foreground: if elapsed > LOCK_TIMEOUT_MS → show biometric prompt
 * - If biometric fails or is cancelled → stays locked (retry button)
 * - If biometric succeeds → app resumes exactly where user was
 * - Does NOT log out the user — session stays alive
 *
 * Usage: wrap in _layout.tsx around the navigator
 *   <AppLockProvider>
 *     <RootNavigator />
 *   </AppLockProvider>
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { AppState, type AppStateStatus, StyleSheet, View, Image, Pressable } from 'react-native';
import { Text } from 'react-native-paper';
import * as LocalAuthentication from 'expo-local-authentication';
import * as ScreenCapture from 'expo-screen-capture';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAuth } from '@core/hooks/use-auth';
import { storage } from '@core/storage/mmkv';

const APP_LOGO = require('../../../assets/images/logo_hd.png');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/** Time in background before requiring biometric unlock (ms) */
const LOCK_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/** MMKV key to persist user preference */
const APP_LOCK_ENABLED_KEY = 'app_lock_enabled';
/** MMKV key to persist background timestamp (survives OOM kill) */
const BG_TIMESTAMP_KEY = 'app_lock_bg_ts';

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface AppLockContextValue {
  isLocked: boolean;
  isAppLockEnabled: boolean;
  isBiometricAvailable: boolean;
  setAppLockEnabled: (enabled: boolean) => void;
}

const AppLockContext = createContext<AppLockContextValue>({
  isLocked: false,
  isAppLockEnabled: false,
  isBiometricAvailable: false,
  setAppLockEnabled: () => {},
});

export const useAppLock = () => useContext(AppLockContext);

// ---------------------------------------------------------------------------
// Lock Screen UI
// ---------------------------------------------------------------------------

function LockScreen({ onUnlock }: { onUnlock: () => void }) {
  const { t } = useTranslation();
  const [error, setError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  // FLAG_SECURE on lock screen — prevent screenshots of the lock overlay
  useEffect(() => {
    ScreenCapture.preventScreenCaptureAsync().catch(() => {});
    return () => { ScreenCapture.allowScreenCaptureAsync().catch(() => {}); };
  }, []);

  const authenticate = useCallback(async () => {
    if (isAuthenticating) return;
    setIsAuthenticating(true);
    setError('');
    try {
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: t('security.unlockPrompt'),
        fallbackLabel: t('security.usePin'),
        cancelLabel: t('common.cancel'),
        disableDeviceFallback: false,
      });
      if (result.success) {
        onUnlock();
      } else {
        setError(result.error === 'user_cancel' ? '' : t('security.verificationFailed'));
      }
    } catch {
      setError(t('security.authError'));
    } finally {
      setIsAuthenticating(false);
    }
  }, [onUnlock, isAuthenticating, t]);

  // Auto-prompt on mount
  useEffect(() => {
    const timer = setTimeout(authenticate, 300);
    return () => clearTimeout(timer);
  }, []);

  return (
    <View style={lockStyles.container}>
      <View style={lockStyles.content}>
        <Image source={APP_LOGO} style={lockStyles.logo} resizeMode="contain" />
        <MaterialCommunityIcons name="lock-outline" size={48} color="#0D6E3F" style={{ marginTop: 24 }} />
        <Text variant="titleMedium" style={lockStyles.title}>
          {t('security.appLocked')}
        </Text>
        <Text variant="bodySmall" style={lockStyles.subtitle}>
          {t('security.verifyIdentity')}
        </Text>

        {error ? (
          <Text variant="bodySmall" style={lockStyles.error}>{error}</Text>
        ) : null}

        <Pressable
          onPress={authenticate}
          style={lockStyles.unlockBtn}
          android_ripple={{ color: 'rgba(13,110,63,0.2)' }}
        >
          <MaterialCommunityIcons name="fingerprint" size={28} color="#0D6E3F" />
          <Text style={lockStyles.unlockText}>{t('security.unlock')}</Text>
        </Pressable>
      </View>
    </View>
  );
}

const lockStyles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: '#F4FBF6',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 9999,
  },
  content: {
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  logo: { width: 120, height: 40 },
  title: { fontWeight: '700', color: '#333', marginTop: 16 },
  subtitle: { color: '#888', marginTop: 4, textAlign: 'center' },
  error: { color: '#D32F2F', marginTop: 12 },
  unlockBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 32,
    paddingVertical: 14,
    paddingHorizontal: 32,
    borderRadius: 16,
    borderWidth: 2,
    borderColor: '#0D6E3F',
  },
  unlockText: { fontSize: 16, fontWeight: '600', color: '#0D6E3F' },
});

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AppLockProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  // On cold start: check if there's a persisted bg timestamp → lock if expired
  const [isLocked, setIsLocked] = useState(() => {
    const ts = storage.getNumber(BG_TIMESTAMP_KEY);
    if (ts) {
      storage.delete(BG_TIMESTAMP_KEY);
      return (Date.now() - ts) >= LOCK_TIMEOUT_MS;
    }
    return false;
  });
  const [isAppLockEnabled, setAppLockEnabledState] = useState(() => {
    return storage.getBoolean(APP_LOCK_ENABLED_KEY) ?? true; // enabled by default
  });
  const [isBiometricAvailable, setIsBiometricAvailable] = useState(false);

  // Check biometric availability
  useEffect(() => {
    LocalAuthentication.hasHardwareAsync().then((has) => {
      if (has) {
        LocalAuthentication.isEnrolledAsync().then(setIsBiometricAvailable);
      }
    });
  }, []);

  const setAppLockEnabled = useCallback((enabled: boolean) => {
    setAppLockEnabledState(enabled);
    storage.set(APP_LOCK_ENABLED_KEY, enabled);
  }, []);

  // AppState listener — track background/foreground transitions
  useEffect(() => {
    if (!isAuthenticated || !isAppLockEnabled || !isBiometricAvailable) return;

    const handleAppStateChange = (nextState: AppStateStatus) => {
      if (nextState === 'background' || nextState === 'inactive') {
        // Persist to MMKV so it survives OOM kill
        storage.set(BG_TIMESTAMP_KEY, Date.now());
      } else if (nextState === 'active') {
        const ts = storage.getNumber(BG_TIMESTAMP_KEY);
        if (ts) {
          storage.delete(BG_TIMESTAMP_KEY);
          const elapsed = Date.now() - ts;
          if (elapsed >= LOCK_TIMEOUT_MS) {
            setIsLocked(true);
          }
        }
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);
    return () => subscription.remove();
  }, [isAuthenticated, isAppLockEnabled, isBiometricAvailable]);

  // Reset lock when user logs out
  useEffect(() => {
    if (!isAuthenticated) {
      setIsLocked(false);
      storage.delete(BG_TIMESTAMP_KEY);
    }
  }, [isAuthenticated]);

  const handleUnlock = useCallback(() => {
    setIsLocked(false);
  }, []);

  return (
    <AppLockContext.Provider value={{ isLocked, isAppLockEnabled, isBiometricAvailable, setAppLockEnabled }}>
      {children}
      {isLocked && <LockScreen onUnlock={handleUnlock} />}
    </AppLockContext.Provider>
  );
}
