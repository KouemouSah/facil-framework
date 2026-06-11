/**
 * Photo Gallery - Swipeable grid with add button
 * Native Android: simple grid, no fancy animations
 */

import React, { useCallback, useState } from 'react';
import { Alert, Image, Modal, Pressable, StyleSheet, View } from 'react-native';
import { IconButton, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

import { useAppTheme } from '@core/theme';
import { capturePhoto, pickPhoto, type PhotoCapture } from '@modules/camera/services/photo-service';

interface Props {
  photos: string[];
  onPhotosChange?: (photos: string[]) => void;
  localPhotos?: PhotoCapture[];
  onLocalPhotosChange?: (photos: PhotoCapture[]) => void;
  readonly?: boolean;
  maxPhotos?: number;
}

export function PhotoGallery({
  photos,
  onPhotosChange,
  localPhotos = [],
  onLocalPhotosChange,
  readonly = false,
  maxPhotos = 10,
}: Props) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const [zoomUri, setZoomUri] = useState<string | null>(null);
  const totalPhotos = photos.length + localPhotos.length;
  const canAdd = !readonly && totalPhotos < maxPhotos;

  const handleAdd = useCallback(() => {
    Alert.alert(
      t('inspection.addPhoto'),
      undefined,
      [
        {
          text: t('inspection.takePhoto'),
          onPress: async () => {
            try {
              const photo = await capturePhoto();
              if (photo && onLocalPhotosChange) {
                onLocalPhotosChange([...localPhotos, photo]);
              }
            } catch (err) {
              Alert.alert(t('common.error'), (err as Error).message);
            }
          },
        },
        {
          text: t('gallery.fromGallery'),
          onPress: async () => {
            try {
              const photo = await pickPhoto();
              if (photo && onLocalPhotosChange) {
                onLocalPhotosChange([...localPhotos, photo]);
              }
            } catch (err) {
              Alert.alert(t('common.error'), (err as Error).message);
            }
          },
        },
        { text: t('common.cancel'), style: 'cancel' },
      ],
    );
  }, [localPhotos, onLocalPhotosChange, t]);

  const handleRemoveLocal = useCallback((index: number) => {
    if (onLocalPhotosChange) {
      const updated = [...localPhotos];
      updated.splice(index, 1);
      onLocalPhotosChange(updated);
    }
  }, [localPhotos, onLocalPhotosChange]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text variant="labelLarge" style={{ color: colors.onSurfaceVariant }}>
          {t('inspection.photos')} ({totalPhotos}/{maxPhotos})
        </Text>
      </View>
      <View style={styles.grid}>
        {/* Remote photos (already uploaded) — tap to zoom */}
        {photos.map((uri) => (
          <Pressable key={uri} style={styles.photoWrapper} onPress={() => setZoomUri(uri)}>
            <Image source={{ uri }} style={styles.photo} resizeMode="cover" />
          </Pressable>
        ))}
        {/* Local photos (not yet uploaded) */}
        {localPhotos.map((photo, i) => (
          <View key={`local-${i}`} style={styles.photoWrapper}>
            <Image source={{ uri: photo.uri }} style={styles.photo} resizeMode="cover" />
            {!readonly && (
              <IconButton
                icon="close-circle"
                size={20}
                iconColor={colors.error}
                style={styles.removeButton}
                onPress={() => handleRemoveLocal(i)}
              />
            )}
            {photo.gps && (
              <View style={styles.gpsBadge}>
                <MaterialCommunityIcons name="map-marker" size={10} color="#fff" />
              </View>
            )}
          </View>
        ))}
        {/* Add button */}
        {canAdd && (
          <Pressable
            onPress={handleAdd}
            style={[styles.addButton, { borderColor: colors.outline }]}
            android_ripple={{ color: colors.surfaceVariant }}
          >
            <MaterialCommunityIcons name="camera-plus" size={28} color={colors.onSurfaceVariant} />
          </Pressable>
        )}
      </View>

      {/* Fullscreen zoom modal */}
      <Modal visible={!!zoomUri} transparent animationType="fade" onRequestClose={() => setZoomUri(null)}>
        <Pressable
          style={styles.zoomOverlay}
          onPress={() => setZoomUri(null)}
        >
          {zoomUri && (
            <Image
              source={{ uri: zoomUri }}
              style={styles.zoomImage}
              resizeMode="contain"
            />
          )}
          <IconButton
            icon="close"
            size={28}
            iconColor="#FFF"
            style={styles.zoomClose}
            onPress={() => setZoomUri(null)}
          />
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: 16 },
  header: { paddingHorizontal: 16, marginBottom: 8 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12, gap: 8 },
  photoWrapper: { width: 96, height: 96, borderRadius: 8, overflow: 'hidden' },
  photo: { width: '100%', height: '100%' },
  removeButton: {
    position: 'absolute',
    top: -4,
    right: -4,
    margin: 0,
    backgroundColor: 'rgba(255,255,255,0.8)',
  },
  gpsBadge: {
    position: 'absolute',
    bottom: 4,
    left: 4,
    backgroundColor: 'rgba(0,0,0,0.5)',
    borderRadius: 8,
    padding: 2,
  },
  addButton: {
    width: 96,
    height: 96,
    borderRadius: 8,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    justifyContent: 'center',
    alignItems: 'center',
  },
  zoomOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.95)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  zoomImage: {
    width: '100%',
    height: '80%',
  },
  zoomClose: {
    position: 'absolute',
    top: 48,
    right: 16,
  },
});
