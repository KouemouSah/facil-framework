/**
 * App Lock - Biometric lock screen after background
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { AppState, type AppStateStatus, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Text } from 'react-native-paper';
import * as LocalAuthentication from 'expo-local-authentication';

import { useTranslation } from 'react-i18next';

import { useAuth } from '@core/hooks/use-auth';
import { getItem, setItem } from '@core/storage/mmkv';
import { useAppTheme } from '@core/theme';

const LOCK_TIMEOUT_MS = 5 * 60 * 1_000;
const BG_TIMESTAMP_KEY = 'inspector_bg_timestamp';

interface AppLockContextValue {
  isLocked: boolean;
}

const AppLockContext = createContext<AppLockContextValue>({ isLocked: false });

export function useAppLock() {
  return useContext(AppLockContext);
}

export function AppLockProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [isLocked, setIsLocked] = useState(false);

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'background') {
        setItem(BG_TIMESTAMP_KEY, Date.now().toString());
      } else if (state === 'active' && isAuthenticated) {
        const bgTime = getItem<string>(BG_TIMESTAMP_KEY);
        if (bgTime && Date.now() - Number(bgTime) > LOCK_TIMEOUT_MS) {
          setIsLocked(true);
        }
      }
    });
    return () => subscription.remove();
  }, [isAuthenticated]);

  const unlock = useCallback(async () => {
    try {
      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      if (!hasHardware) {
        setIsLocked(false);
        return;
      }
      const result = await LocalAuthentication.authenticateAsync({
        promptMessage: t('lock.unlockTitle'),
        cancelLabel: t('common.cancel'),
        disableDeviceFallback: false,
      });
      if (result.success) setIsLocked(false);
    } catch {
      setIsLocked(false);
    }
  }, []);

  if (isLocked && isAuthenticated) {
    return (
      <View style={[styles.lockScreen, { backgroundColor: colors.background }]}>
        <Text variant="headlineMedium" style={{ color: colors.primary, marginBottom: 16 }}>
          {t('lock.appName')}
        </Text>
        <Text variant="bodyLarge" style={{ color: colors.onBackground, marginBottom: 32 }}>
          {t('lock.locked')}
        </Text>
        <Button mode="contained" onPress={unlock}>{t('lock.unlock')}</Button>
      </View>
    );
  }

  return (
    <AppLockContext.Provider value={{ isLocked }}>
      {children}
    </AppLockContext.Provider>
  );
}

const styles = StyleSheet.create({
  lockScreen: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
});
