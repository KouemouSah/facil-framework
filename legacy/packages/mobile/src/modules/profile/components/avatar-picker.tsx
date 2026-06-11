/**
 * Avatar Picker
 *
 * Bottom sheet modal with 3 options:
 * - Take Photo (camera)
 * - Choose from Gallery
 * - Remove Avatar
 *
 * Uses expo-image-picker with image compression (max 1MB for mobile networks).
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Modal, Portal, Button, Text, Divider, useTheme } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';

interface AvatarPickerProps {
  visible: boolean;
  onDismiss: () => void;
  onImageSelected: (uri: string) => void;
  onRemove: () => void;
  hasAvatar: boolean;
}

/**
 * Compress image to max 1MB (suitable for mobile networks in GE).
 * Resizes to 512x512 and compresses as JPEG.
 */
async function compressImage(uri: string): Promise<string> {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: 512, height: 512 } }],
    { compress: 0.8, format: ImageManipulator.SaveFormat.JPEG },
  );
  return result.uri;
}

export function AvatarPicker({
  visible,
  onDismiss,
  onImageSelected,
  onRemove,
  hasAvatar,
}: AvatarPickerProps) {
  const theme = useTheme();
  const { t } = useTranslation();

  const handleCamera = async () => {
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') return;

    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      const compressed = await compressImage(result.assets[0].uri);
      onImageSelected(compressed);
      onDismiss();
    }
  };

  const handleGallery = async () => {
    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') return;

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      const compressed = await compressImage(result.assets[0].uri);
      onImageSelected(compressed);
      onDismiss();
    }
  };

  const handleRemove = () => {
    onRemove();
    onDismiss();
  };

  return (
    <Portal>
      <Modal
        visible={visible}
        onDismiss={onDismiss}
        contentContainerStyle={[
          styles.modal,
          { backgroundColor: theme.colors.surface, borderRadius: 16 },
        ]}
      >
        <Text variant="titleMedium" style={[styles.title, { color: theme.colors.onSurface }]}>
          {t('profile.changeAvatar')}
        </Text>
        <Divider style={{ marginBottom: 8 }} />

        <View style={styles.options}>
          <Button
            mode="text"
            icon="camera"
            onPress={handleCamera}
            contentStyle={styles.optionContent}
            style={styles.option}
          >
            {t('profile.takePhoto')}
          </Button>
          <Button
            mode="text"
            icon="image"
            onPress={handleGallery}
            contentStyle={styles.optionContent}
            style={styles.option}
          >
            {t('profile.chooseFromGallery')}
          </Button>
          {hasAvatar && (
            <Button
              mode="text"
              icon="delete-outline"
              onPress={handleRemove}
              contentStyle={styles.optionContent}
              style={styles.option}
              textColor={theme.colors.error}
            >
              {t('profile.removeAvatar')}
            </Button>
          )}
        </View>

        <Button mode="outlined" onPress={onDismiss} style={{ marginTop: 8 }}>
          {t('common.cancel')}
        </Button>
      </Modal>
    </Portal>
  );
}

const styles = StyleSheet.create({
  modal: {
    margin: 24,
    padding: 20,
  },
  title: {
    fontWeight: '600',
    marginBottom: 12,
    textAlign: 'center',
  },
  options: {
    gap: 4,
  },
  option: {
    alignItems: 'flex-start',
  },
  optionContent: {
    justifyContent: 'flex-start',
  },
});
