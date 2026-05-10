/**
 * Language Picker
 *
 * Bottom sheet modal with radio buttons for ES/FR/EN.
 * On selection: updates i18n + backend + MMKV + API client locale.
 */

import React, { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Modal, Portal, Button, RadioButton, Text, Divider, useTheme } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { setApiLocale } from '@core/api/client';
import type { SupportedLanguage } from '@core/config/types';
import { useUpdateProfile } from '../services/profile-hooks';

interface LanguagePickerProps {
  visible: boolean;
  onDismiss: () => void;
  currentLanguage: SupportedLanguage;
  onLanguageChanged: (lang: SupportedLanguage) => void;
}

const LANGUAGES: { code: SupportedLanguage; label: string; flag: string }[] = [
  { code: 'es', label: 'Español', flag: '🇬🇶' },
  { code: 'fr', label: 'Français', flag: '🇫🇷' },
  { code: 'en', label: 'English', flag: '🇬🇧' },
];

export function LanguagePicker({
  visible,
  onDismiss,
  currentLanguage,
  onLanguageChanged,
}: LanguagePickerProps) {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const updateMutation = useUpdateProfile();
  const [selected, setSelected] = useState<SupportedLanguage>(currentLanguage);

  const handleConfirm = async () => {
    if (selected === currentLanguage) {
      onDismiss();
      return;
    }

    // 1. Update i18n locale
    await i18n.changeLanguage(selected);

    // 2. Update API client locale header
    setApiLocale(selected);

    // 3. Persist to backend
    updateMutation.mutate({ preferred_language: selected });

    // 4. Notify parent (updates local state)
    onLanguageChanged(selected);

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
          {t('profile.languageTitle')}
        </Text>
        <Divider style={{ marginBottom: 8 }} />

        <RadioButton.Group onValueChange={(v) => setSelected(v as SupportedLanguage)} value={selected}>
          {LANGUAGES.map(({ code, label, flag }) => (
            <RadioButton.Item
              key={code}
              label={`${flag}  ${label}`}
              value={code}
              style={styles.radioItem}
              labelStyle={{ fontSize: 16 }}
            />
          ))}
        </RadioButton.Group>

        <View style={styles.actions}>
          <Button mode="outlined" onPress={onDismiss} style={{ flex: 1, marginRight: 8 }}>
            {t('common.cancel')}
          </Button>
          <Button
            mode="contained"
            onPress={handleConfirm}
            loading={updateMutation.isPending}
            style={{ flex: 1 }}
          >
            {t('common.confirm')}
          </Button>
        </View>
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
  radioItem: {
    paddingVertical: 4,
  },
  actions: {
    flexDirection: 'row',
    marginTop: 16,
  },
});
