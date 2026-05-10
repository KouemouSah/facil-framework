/**
 * Photo Service - Camera capture and gallery pick
 *
 * Uses expo-image-picker for both camera and gallery.
 * Compresses images to max 1920px, 70% quality.
 */

import * as ImagePicker from 'expo-image-picker';
import { appConfig } from '@core/config/app';

export interface PhotoCapture {
  uri: string;
  width: number;
  height: number;
  gps?: {
    latitude: number;
    longitude: number;
  };
}

const IMAGE_OPTIONS: ImagePicker.ImagePickerOptions = {
  mediaTypes: ['images'],
  quality: appConfig.upload.compressionQuality,
  allowsEditing: false,
  exif: true,
};

/** Capture a photo using the device camera */
export async function capturePhoto(): Promise<PhotoCapture | null> {
  const { status } = await ImagePicker.requestCameraPermissionsAsync();
  if (status !== 'granted') {
    throw new Error('CAMERA_PERMISSION_DENIED');
  }

  const result = await ImagePicker.launchCameraAsync(IMAGE_OPTIONS);
  if (result.canceled || result.assets.length === 0) return null;

  const asset = result.assets[0];
  return {
    uri: asset.uri,
    width: asset.width,
    height: asset.height,
    gps: asset.exif?.GPSLatitude && asset.exif?.GPSLongitude
      ? {
          latitude: asset.exif.GPSLatitude as number,
          longitude: asset.exif.GPSLongitude as number,
        }
      : undefined,
  };
}

/** Pick a photo from the device gallery */
export async function pickPhoto(): Promise<PhotoCapture | null> {
  const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (status !== 'granted') {
    throw new Error('GALLERY_PERMISSION_DENIED');
  }

  const result = await ImagePicker.launchImageLibraryAsync(IMAGE_OPTIONS);
  if (result.canceled || result.assets.length === 0) return null;

  const asset = result.assets[0];
  return {
    uri: asset.uri,
    width: asset.width,
    height: asset.height,
    gps: asset.exif?.GPSLatitude && asset.exif?.GPSLongitude
      ? {
          latitude: asset.exif.GPSLatitude as number,
          longitude: asset.exif.GPSLongitude as number,
        }
      : undefined,
  };
}
