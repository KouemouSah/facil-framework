/**
 * Signature Pad Component
 *
 * Full-width canvas for agent signatures.
 * Exports base64 PNG + SHA-256 hash for tamper detection.
 * Uses react-native-signature-canvas (WebView-based).
 *
 * OWASP A08: Hash is computed client-side and verified server-side.
 */

import React, { useCallback, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import SignatureScreen, { type SignatureViewRef } from 'react-native-signature-canvas';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { hashSignature } from '@core/utils/crypto';
import { useAuth } from '@core/hooks/use-auth';

export interface SignatureResult {
  /** Base64 encoded PNG image (data:image/png;base64,...) */
  base64: string;
  /** SHA-256 hash for tamper detection */
  hash: string;
  /** Timestamp when signature was captured */
  timestamp: string;
}

interface Props {
  /** Called when signature is confirmed */
  onSignature: (result: SignatureResult) => void;
  /** Called when signature is cleared */
  onClear?: () => void;
  /** Height of the signature area (default 200) */
  height?: number;
  /** Whether the pad is disabled */
  disabled?: boolean;
}

export function SignaturePad({ onSignature, onClear, height = 200, disabled = false }: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const { user } = useAuth();
  const signRef = useRef<SignatureViewRef>(null);

  const [hasContent, setHasContent] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleEnd = useCallback(() => {
    setHasContent(true);
  }, []);

  const handleClear = useCallback(() => {
    signRef.current?.clearSignature();
    setHasContent(false);
    setIsConfirmed(false);
    onClear?.();
  }, [onClear]);

  const handleConfirm = useCallback(() => {
    if (!hasContent) return;
    signRef.current?.readSignature();
  }, [hasContent]);

  const handleOK = useCallback(async (signature: string) => {
    if (isProcessing) return;
    setIsProcessing(true);

    try {
      const userId = user?.id ?? 'unknown';
      const hash = await hashSignature(signature, userId);
      const timestamp = new Date().toISOString();

      setIsConfirmed(true);
      onSignature({ base64: signature, hash, timestamp });
    } finally {
      setIsProcessing(false);
    }
  }, [user?.id, onSignature, isProcessing]);

  const handleEmpty = useCallback(() => {
    setHasContent(false);
  }, []);

  // Signature canvas style — always white background with dark stroke
  // for readability on the signed document (regardless of app dark mode)
  const webStyle = `.m-signature-pad {
    box-shadow: none;
    border: none;
    margin: 0;
    padding: 0;
  }
  .m-signature-pad--body {
    border: none;
    margin: 0;
  }
  .m-signature-pad--footer { display: none; }
  body { margin: 0; padding: 0; background: #FAFAFA; }
  canvas {
    width: 100%;
    height: 100%;
  }`;

  return (
    <View style={styles.container}>
      {/* Canvas */}
      <View style={[styles.canvasContainer, { height, borderColor: colors.outline }]}>
        {isConfirmed ? (
          <View style={[styles.confirmedOverlay, { backgroundColor: '#FAFAFA' }]}>
            <Text variant="bodyMedium" style={{ color: '#2E7D32' }}>
              {t('complete.signatureRecorded')}
            </Text>
          </View>
        ) : (
          <SignatureScreen
            ref={signRef}
            onEnd={handleEnd}
            onOK={handleOK}
            onEmpty={handleEmpty}
            webStyle={webStyle}
            backgroundColor="#FAFAFA"
            penColor="#1A1A1A"
            dotSize={2}
            minWidth={1.5}
            maxWidth={3}
            trimWhitespace={true}
            imageType="image/png"
            dataURL="data:image/png;base64,"
            style={styles.canvas}
          />
        )}

        {/* Instruction text when empty */}
        {!hasContent && !isConfirmed && (
          <View style={styles.placeholder} pointerEvents="none">
            <Text variant="bodySmall" style={{ color: '#9E9E9E' }}>
              {t('complete.signatureTap')}
            </Text>
          </View>
        )}
      </View>

      {/* Action buttons */}
      <View style={styles.actions}>
        <Button
          mode="text"
          icon="eraser"
          onPress={handleClear}
          disabled={disabled || (!hasContent && !isConfirmed)}
          textColor={colors.error}
          compact
        >
          {t('common.delete')}
        </Button>

        {!isConfirmed && (
          <Button
            mode="contained"
            icon="check"
            onPress={handleConfirm}
            disabled={disabled || !hasContent || isProcessing}
            loading={isProcessing}
            compact
          >
            {t('common.confirm')}
          </Button>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {},
  canvasContainer: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: 8,
    overflow: 'hidden',
    position: 'relative',
  },
  canvas: {
    flex: 1,
  },
  confirmedOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholder: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
});
