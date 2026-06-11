/**
 * QR Scanner Component
 *
 * Full-screen camera view with barcode scanning overlay.
 * Uses expo-camera CameraView (SDK 54) with native barcode detection.
 * Debounced to prevent duplicate reads.
 */

import React, { useCallback, useRef, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { Button, IconButton, Text } from 'react-native-paper';
import { CameraView, useCameraPermissions, type BarcodeScanningResult } from 'expo-camera';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

interface QRScannerProps {
  onScan: (data: string) => void;
  onClose: () => void;
}

const SCAN_DEBOUNCE_MS = 2000;

export function QRScanner({ onScan, onClose }: QRScannerProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const [permission, requestPermission] = useCameraPermissions();
  const [torch, setTorch] = useState(false);
  const lastScanRef = useRef<number>(0);

  const handleBarCodeScanned = useCallback(
    (result: BarcodeScanningResult) => {
      const now = Date.now();
      if (now - lastScanRef.current < SCAN_DEBOUNCE_MS) return;
      lastScanRef.current = now;
      onScan(result.data);
    },
    [onScan],
  );

  // Permission not yet determined
  if (!permission) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <Text variant="bodyLarge" style={{ color: colors.onBackground }}>
          {t('scanner.permissionRequired')}
        </Text>
      </View>
    );
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <View style={[styles.container, styles.permissionView, { backgroundColor: colors.background }]}>
        <Text variant="titleMedium" style={{ color: colors.onBackground, textAlign: 'center', marginBottom: 16 }}>
          {t('scanner.permissionDenied')}
        </Text>
        {permission.canAskAgain ? (
          <Button mode="contained" onPress={requestPermission}>
            {t('scanner.permissionRequired')}
          </Button>
        ) : (
          <Button mode="contained" onPress={() => Linking.openSettings()}>
            {t('scanner.openSettings')}
          </Button>
        )}
        <Button mode="text" onPress={onClose} style={{ marginTop: 12 }}>
          {t('common.cancel')}
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        enableTorch={torch}
        barcodeScannerSettings={{
          barcodeTypes: ['qr'],
        }}
        onBarcodeScanned={handleBarCodeScanned}
      />

      {/* Overlay */}
      <View style={styles.overlay}>
        {/* Top bar */}
        <View style={styles.topBar}>
          <IconButton
            icon="close"
            size={28}
            iconColor="#FFFFFF"
            onPress={onClose}
          />
          <Text variant="titleMedium" style={styles.title}>
            {t('scanner.title')}
          </Text>
          <IconButton
            icon={torch ? 'flashlight-off' : 'flashlight'}
            size={28}
            iconColor="#FFFFFF"
            onPress={() => setTorch((prev) => !prev)}
          />
        </View>

        {/* Visor frame */}
        <View style={styles.visorContainer}>
          <View style={styles.visor}>
            {/* Corner brackets */}
            <View style={[styles.corner, styles.topLeft]} />
            <View style={[styles.corner, styles.topRight]} />
            <View style={[styles.corner, styles.bottomLeft]} />
            <View style={[styles.corner, styles.bottomRight]} />
          </View>
        </View>

        {/* Instruction text */}
        <View style={styles.bottomBar}>
          <Text variant="bodyMedium" style={styles.instruction}>
            {t('scanner.instruction')}
          </Text>
        </View>
      </View>
    </View>
  );
}

const VISOR_SIZE = 260;
const CORNER_SIZE = 32;
const CORNER_WIDTH = 4;
const CORNER_COLOR = '#FFFFFF';

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  permissionView: {
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'transparent',
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 48,
    paddingHorizontal: 8,
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  title: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  visorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  visor: {
    width: VISOR_SIZE,
    height: VISOR_SIZE,
    position: 'relative',
  },
  corner: {
    position: 'absolute',
    width: CORNER_SIZE,
    height: CORNER_SIZE,
  },
  topLeft: {
    top: 0,
    left: 0,
    borderTopWidth: CORNER_WIDTH,
    borderLeftWidth: CORNER_WIDTH,
    borderColor: CORNER_COLOR,
    borderTopLeftRadius: 4,
  },
  topRight: {
    top: 0,
    right: 0,
    borderTopWidth: CORNER_WIDTH,
    borderRightWidth: CORNER_WIDTH,
    borderColor: CORNER_COLOR,
    borderTopRightRadius: 4,
  },
  bottomLeft: {
    bottom: 0,
    left: 0,
    borderBottomWidth: CORNER_WIDTH,
    borderLeftWidth: CORNER_WIDTH,
    borderColor: CORNER_COLOR,
    borderBottomLeftRadius: 4,
  },
  bottomRight: {
    bottom: 0,
    right: 0,
    borderBottomWidth: CORNER_WIDTH,
    borderRightWidth: CORNER_WIDTH,
    borderColor: CORNER_COLOR,
    borderBottomRightRadius: 4,
  },
  bottomBar: {
    padding: 24,
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.4)',
  },
  instruction: {
    color: '#FFFFFF',
    textAlign: 'center',
  },
});
