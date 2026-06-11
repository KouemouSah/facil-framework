/**
 * Profile API Service
 *
 * Thin wrappers for user profile endpoints.
 * Screens should use profile-hooks.ts instead.
 */

import { apiGet, apiPut, apiPost, apiDelete, apiUpload } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import type {
  UserProfile,
  UserUpdateRequest,
  ProfilePasswordChangeResponse,
} from '@core/config/types';
import { Platform } from 'react-native';

// ---------------------------------------------------------------------------
// Profile CRUD
// ---------------------------------------------------------------------------

/** GET /users/profile */
export async function getProfile(): Promise<UserProfile> {
  return apiGet<UserProfile>(API_ENDPOINTS.users.profile);
}

/** PUT /users/profile */
export async function updateProfile(
  data: UserUpdateRequest,
): Promise<UserProfile> {
  return apiPut<UserProfile>(API_ENDPOINTS.users.updateProfile, data);
}

// ---------------------------------------------------------------------------
// Password
// ---------------------------------------------------------------------------

/** POST /users/profile/change-password */
export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<ProfilePasswordChangeResponse> {
  return apiPost<ProfilePasswordChangeResponse>(
    API_ENDPOINTS.users.changePassword,
    { old_password: oldPassword, new_password: newPassword },
  );
}

// ---------------------------------------------------------------------------
// Avatar
// ---------------------------------------------------------------------------

/**
 * POST /users/profile/avatar
 * Uploads an image file as multipart/form-data.
 *
 * @param uri - Local file URI from expo-image-picker
 * @param onProgress - Optional upload progress callback (0-1)
 */
export async function uploadAvatar(
  uri: string,
  onProgress?: (progress: number) => void,
): Promise<UserProfile> {
  const formData = new FormData();

  // Extract filename and type from URI
  const filename = uri.split('/').pop() ?? 'avatar.jpg';
  const match = /\.(\w+)$/.exec(filename);
  const type = match ? `image/${match[1] === 'jpg' ? 'jpeg' : match[1]}` : 'image/jpeg';

  // React Native FormData accepts this shape for file uploads
  formData.append('file', {
    uri: Platform.OS === 'android' ? uri : uri.replace('file://', ''),
    name: filename,
    type,
  } as unknown as Blob);

  return apiUpload<UserProfile>(
    API_ENDPOINTS.users.uploadAvatar,
    formData,
    onProgress,
  );
}

/** DELETE /users/profile/avatar */
export async function deleteAvatar(): Promise<UserProfile> {
  return apiDelete<UserProfile>(API_ENDPOINTS.users.deleteAvatar);
}
