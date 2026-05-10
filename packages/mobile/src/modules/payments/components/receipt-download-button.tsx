/**
 * ReceiptDownloadButton — opens the vault-stored payment receipt PDF.
 *
 * Strategy: payment receipts are auto-deposited in the user's vault at backend
 * payment-completion time (`receipt_service.py:805-970`, generation_type='payment_receipt').
 * This component resolves the matching vault document by `service_request_id`,
 * fetches a 15-min signed URL via `useDownloadUrl`, and opens it with
 * `expo-web-browser`. Disabled while resolving or when no receipt exists yet.
 */

import { useMemo, useState } from 'react';
import { Button, Snackbar } from 'react-native-paper';
import * as WebBrowser from 'expo-web-browser';
import { useTranslation } from 'react-i18next';

import { useVaultGenerated, useDownloadUrl } from '@modules/vault';

interface ReceiptDownloadButtonProps {
  /** Service request ID linked to the payment. */
  serviceRequestId: string | null | undefined;
  disabled?: boolean;
}

export function ReceiptDownloadButton({
  serviceRequestId,
  disabled,
}: ReceiptDownloadButtonProps) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);

  const generatedQuery = useVaultGenerated({ generation_type: 'payment_receipt' });

  const matchingReceiptId = useMemo<string | null>(() => {
    if (!serviceRequestId) return null;
    const pages = generatedQuery.data?.pages ?? [];
    for (const page of pages) {
      for (const item of page) {
        if (item.service_request_id === serviceRequestId) return item.id;
      }
    }
    return null;
  }, [generatedQuery.data, serviceRequestId]);

  const downloadQuery = useDownloadUrl(matchingReceiptId);

  const handlePress = async () => {
    if (!downloadQuery.data?.url) return;
    setOpening(true);
    try {
      await WebBrowser.openBrowserAsync(downloadQuery.data.url);
    } catch {
      setError(t('payments.receipt.openError', 'No se pudo abrir el recibo'));
    } finally {
      setOpening(false);
    }
  };

  const isLoading = generatedQuery.isLoading || downloadQuery.isLoading;
  const isDisabled =
    disabled || !matchingReceiptId || !downloadQuery.data?.url || opening;

  return (
    <>
      <Button
        mode="contained"
        icon="receipt"
        loading={isLoading || opening}
        disabled={isDisabled}
        onPress={handlePress}
      >
        {matchingReceiptId
          ? t('payments.receipt.download', 'Descargar recibo')
          : t('payments.receipt.unavailable', 'Recibo no disponible')}
      </Button>
      <Snackbar
        visible={!!error}
        onDismiss={() => setError(null)}
        duration={3500}
      >
        {error ?? ''}
      </Snackbar>
    </>
  );
}
