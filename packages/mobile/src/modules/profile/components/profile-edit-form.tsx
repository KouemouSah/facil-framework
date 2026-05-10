/**
 * Profile Edit Form
 *
 * Editable fields for user profile data.
 * Uses react-hook-form + Zod aligned with backend UserUpdate model.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { TextInput, Button, HelperText } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

import { profileUpdateSchema, type ProfileUpdateInput } from '../validations';
import type { UserProfile } from '@core/config/types';

interface ProfileEditFormProps {
  user: UserProfile;
  onSave: (data: ProfileUpdateInput) => void;
  onCancel: () => void;
  isSaving: boolean;
}

export function ProfileEditForm({ user, onSave, onCancel, isSaving }: ProfileEditFormProps) {
  const { t } = useTranslation();

  const {
    control,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<ProfileUpdateInput>({
    resolver: zodResolver(profileUpdateSchema),
    defaultValues: {
      first_name: user.first_name,
      last_name: user.last_name,
      phone_number: user.phone_number ?? '',
      address: user.address ?? '',
      city: user.city ?? '',
      preferred_language: user.preferred_language,
    },
  });

  return (
    <View style={styles.container}>
      {/* First Name */}
      <Controller
        control={control}
        name="first_name"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.field}>
            <TextInput
              label={t('auth.firstName')}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              mode="outlined"
              autoCapitalize="words"
              error={!!errors.first_name}
              left={<TextInput.Icon icon="account-outline" />}
            />
            {errors.first_name && (
              <HelperText type="error" visible>
                {t(errors.first_name.message ?? '')}
              </HelperText>
            )}
          </View>
        )}
      />

      {/* Last Name */}
      <Controller
        control={control}
        name="last_name"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.field}>
            <TextInput
              label={t('auth.lastName')}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              mode="outlined"
              autoCapitalize="words"
              error={!!errors.last_name}
              left={<TextInput.Icon icon="account-outline" />}
            />
            {errors.last_name && (
              <HelperText type="error" visible>
                {t(errors.last_name.message ?? '')}
              </HelperText>
            )}
          </View>
        )}
      />

      {/* Phone */}
      <Controller
        control={control}
        name="phone_number"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.field}>
            <TextInput
              label={t('auth.phone')}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              mode="outlined"
              keyboardType="phone-pad"
              maxLength={9}
              placeholder="222XXXXXX"
              error={!!errors.phone_number}
              left={<TextInput.Icon icon="phone-outline" />}
            />
            <HelperText
              type={errors.phone_number ? 'error' : 'info'}
              visible
            >
              {errors.phone_number
                ? t(errors.phone_number.message ?? '')
                : t('auth.phoneHintGE')}
            </HelperText>
          </View>
        )}
      />

      {/* Address */}
      <Controller
        control={control}
        name="address"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.field}>
            <TextInput
              label={t('profile.address')}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              mode="outlined"
              error={!!errors.address}
              left={<TextInput.Icon icon="map-marker-outline" />}
            />
            {errors.address && (
              <HelperText type="error" visible>
                {t(errors.address.message ?? '')}
              </HelperText>
            )}
          </View>
        )}
      />

      {/* City */}
      <Controller
        control={control}
        name="city"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.field}>
            <TextInput
              label={t('profile.city')}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              mode="outlined"
              error={!!errors.city}
              left={<TextInput.Icon icon="city-variant-outline" />}
            />
            {errors.city && (
              <HelperText type="error" visible>
                {t(errors.city.message ?? '')}
              </HelperText>
            )}
          </View>
        )}
      />

      {/* Actions */}
      <View style={styles.actions}>
        <Button mode="outlined" onPress={onCancel} style={{ flex: 1, marginRight: 8 }}>
          {t('common.cancel')}
        </Button>
        <Button
          mode="contained"
          onPress={handleSubmit(onSave)}
          loading={isSaving}
          disabled={isSaving || !isDirty}
          style={{ flex: 1 }}
        >
          {t('profile.saveChanges')}
        </Button>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    gap: 4,
  },
  field: {
    marginBottom: 4,
  },
  actions: {
    flexDirection: 'row',
    marginTop: 16,
  },
});
