/**
 * Entry Redirect
 *
 * 1. If first launch → onboarding
 * 2. If auth loading → branded loading screen (green + logo)
 * 3. Otherwise → (tabs)
 */

import { View, ActivityIndicator } from 'react-native';
import { Image } from 'expo-image';
import { Redirect } from 'expo-router';

import { useAuth } from '@core/hooks/use-auth';
import { storage } from '@core/storage/mmkv';

const ONBOARDING_KEY = 'onboarding_completed';
const APP_LOGO = require('../../assets/images/logo_hd.png');

export default function Index() {
  const { isLoading } = useAuth();

  // Check onboarding flag (sync read from MMKV — instant)
  const onboardingCompleted = storage.getBoolean(ONBOARDING_KEY) ?? false;

  if (!onboardingCompleted) {
    return <Redirect href="/onboarding" />;
  }

  if (isLoading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: 'center',
          alignItems: 'center',
          backgroundColor: '#fff',
        }}
      >
        <Image
          source={APP_LOGO}
          style={{ width: 140, height: 46, marginBottom: 24 }}
          contentFit="contain"
          cachePolicy="memory-disk"
          transition={150}
        />
        <ActivityIndicator size="large" color="#0D6E3F" />
      </View>
    );
  }

  return <Redirect href="/(tabs)" />;
}
