/**
 * Image compression and validation utilities for Facil Mobile
 *
 * Uses expo-image-manipulator to resize and compress images before upload.
 * Designed for document photos captured on mobile (ID cards, contracts, etc.)
 * where quality matters but file size must be kept reasonable for mobile networks.
 *
 * Upload constraints are sourced from appConfig.upload (single source of truth).
 *
 * NOTE: Uses the new expo-file-system File API (SDK 54+), NOT the legacy
 * getInfoAsync(). The File class exposes a synchronous `.size` property.
 */

import * as ImageManipulator from 'expo-image-manipulator';
import { File as ExpoFile } from 'expo-file-system';
import { appConfig } from '@core/config/app';

// ---------------------------------------------------------------------------
// Image compression
// ---------------------------------------------------------------------------

/**
 * Compress and resize an image for upload.
 *
 * - Resizes the longest side to at most appConfig.upload.maxImageDimensionPx
 *   (currently 2048px), preserving aspect ratio
 * - Compresses as JPEG at appConfig.upload.compressionQuality (currently 0.8)
 * - Returns the URI of the compressed image (in app cache directory)
 *
 * @param uri - Local file URI of the source image
 * @returns URI of the compressed image
 *
 * @example
 * const compressed = await compressImage(photoResult.uri);
 * await uploadDocument(compressed);
 */
export async function compressImage(uri: string): Promise<string> {
  const result = await ImageManipulator.manipulateAsync(
    uri,
    [{ resize: { width: appConfig.upload.maxImageDimensionPx } }],
    {
      compress: appConfig.upload.compressionQuality,
      format: ImageManipulator.SaveFormat.JPEG,
    },
  );

  return result.uri;
}

// ---------------------------------------------------------------------------
// File size utilities
// ---------------------------------------------------------------------------

/**
 * Get the file size of a local file in megabytes.
 *
 * Uses the new expo-file-system File API (SDK 54+). The `.size` property
 * returns bytes synchronously (0 if the file does not exist).
 *
 * @param uri - Local file URI (file:// scheme)
 * @returns File size in MB (e.g. 2.45)
 * @throws If the file does not exist
 */
export function getFileSizeMB(uri: string): number {
  const file = new ExpoFile(uri);

  if (!file.exists) {
    throw new Error(`File not found: ${uri}`);
  }

  const sizeBytes = file.size;
  return sizeBytes / (1024 * 1024);
}

/**
 * Check if a file size (in MB) is within the allowed upload limit
 * defined in appConfig.upload.maxFileSizeMB.
 *
 * @param sizeMB - File size in megabytes
 * @returns true if size is within limit
 */
export function isFileSizeValid(sizeMB: number): boolean {
  return sizeMB > 0 && sizeMB <= appConfig.upload.maxFileSizeMB;
}

// ---------------------------------------------------------------------------
// Combined validation + compression
// ---------------------------------------------------------------------------

/**
 * Compress an image and validate its final size.
 *
 * @param uri - Local file URI of the source image
 * @returns Object with the compressed URI and size in MB
 * @throws If the compressed file exceeds the maximum allowed size
 */
export async function compressAndValidate(
  uri: string,
): Promise<{ uri: string; sizeMB: number }> {
  const compressedUri = await compressImage(uri);
  const sizeMB = getFileSizeMB(compressedUri);

  if (!isFileSizeValid(sizeMB)) {
    throw new Error(
      `Compressed image is ${sizeMB.toFixed(1)} MB, which exceeds the ${appConfig.upload.maxFileSizeMB} MB limit.`,
    );
  }

  return { uri: compressedUri, sizeMB };
}
