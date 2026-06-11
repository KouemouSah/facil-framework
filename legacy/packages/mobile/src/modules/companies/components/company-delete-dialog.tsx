import React, { useState } from 'react';
import { Button, Dialog, Portal, Text, TextInput } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

interface CompanyDeleteDialogProps {
  visible: boolean;
  companyName: string;
  loading?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Type-name-to-confirm dialog. Hard delete is irreversible (CASCADE on
 * user_company_roles), so the gate is intentionally noisy.
 */
export function CompanyDeleteDialog({
  visible,
  companyName,
  loading,
  onCancel,
  onConfirm,
}: CompanyDeleteDialogProps) {
  const { t } = useTranslation();
  const [typed, setTyped] = useState('');
  const matches = typed.trim().toLowerCase() === companyName.trim().toLowerCase();

  return (
    <Portal>
      <Dialog visible={visible} onDismiss={onCancel}>
        <Dialog.Title>{t('companies.delete.title')}</Dialog.Title>
        <Dialog.Content>
          <Text variant="bodyMedium" style={{ marginBottom: 12 }}>
            {t('companies.delete.body', { name: companyName })}
          </Text>
          <TextInput
            value={typed}
            onChangeText={setTyped}
            mode="outlined"
            autoCapitalize="none"
            placeholder={companyName}
            label={t('companies.delete.placeholder')}
          />
        </Dialog.Content>
        <Dialog.Actions>
          <Button onPress={onCancel}>{t('common.cancel')}</Button>
          <Button
            onPress={onConfirm}
            disabled={!matches || loading}
            loading={loading}
            buttonColor="#D32F2F"
            textColor="white"
            mode="contained"
          >
            {t('companies.delete.confirm')}
          </Button>
        </Dialog.Actions>
      </Dialog>
    </Portal>
  );
}
