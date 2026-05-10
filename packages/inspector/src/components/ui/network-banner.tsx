/**
 * Network Banner — Persistent warning when device is offline.
 * Shows at the top of the screen, auto-hides when connection returns.
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useNetwork } from '@core/hooks/use-network';

export function NetworkBanner() {
  const { t } = useTranslation();
  const { isConnected } = useNetwork();

  if (isConnected !== false) return null;

  return (
    <View style={styles.banner}>
      <MaterialCommunityIcons name="wifi-off" size={16} color="#FFF" />
      <Text variant="labelMedium" style={styles.text}>
        {t('errors.network')}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#C62828',
    paddingVertical: 6,
    paddingHorizontal: 16,
  },
  text: {
    color: '#FFF',
    fontWeight: '600',
  },
});
