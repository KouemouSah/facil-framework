/**
 * ReceiptSuccessDialog
 * Shown after an agent successfully validates a payment.
 * Displays receipt number and offers Download PDF / Print actions.
 * Downloads the PDF from the backend endpoint (no Firebase dependency).
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CheckCircle, Download, Printer, Loader2 } from 'lucide-react';
import { getAuthData } from '@/core/auth/storage';
import { appConfig } from '@/core/config/app';
import { toast } from '@/hooks/use-toast';

interface ReceiptSuccessDialogProps {
  open: boolean;
  onClose: () => void;
  receiptNumber: string;
  paymentId: string;
}

async function fetchReceiptBlob(paymentId: string): Promise<Blob> {
  const authData = getAuthData();
  const baseUrl = `${appConfig.api.baseUrl}/api/v1`;
  const url = `${baseUrl}/admin/service-requests/treasury/payments/${paymentId}/receipt/download`;

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${authData?.access_token || ''}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to download receipt: ${response.status}`);
  }

  return response.blob();
}

export function ReceiptSuccessDialog({
  open,
  onClose,
  receiptNumber,
  paymentId,
}: ReceiptSuccessDialogProps) {
  const t = useTranslations('treasury');
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await fetchReceiptBlob(paymentId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `recibo_${receiptNumber}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Receipt download failed:', error);
      toast({ title: 'Error', description: t('receipt.downloadError'), variant: 'destructive' });
    } finally {
      setDownloading(false);
    }
  };

  const handlePrint = async () => {
    setDownloading(true);
    try {
      const blob = await fetchReceiptBlob(paymentId);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Receipt print failed:', error);
      toast({ title: 'Error', description: t('receipt.printError'), variant: 'destructive' });
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-500" />
            {t('receipt.successTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('receipt.successDescription')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center justify-center py-4">
          <div className="text-center space-y-1">
            <p className="text-xs text-muted-foreground">{t('receipt.receiptNumber')}</p>
            <p className="text-lg font-mono font-bold">{receiptNumber}</p>
          </div>
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button variant="outline" onClick={handleDownload} disabled={downloading} className="flex-1">
            {downloading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
            {t('receipt.download')}
          </Button>
          <Button variant="outline" onClick={handlePrint} disabled={downloading} className="flex-1">
            {downloading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Printer className="h-4 w-4 mr-2" />}
            {t('receipt.print')}
          </Button>
          <Button onClick={onClose} className="flex-1">
            {t('receipt.continue')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
