/**
 * Payment Validation Dialog
 * Modal for validating (approving) a payment
 */

'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { CheckCircle, Loader2 } from 'lucide-react';
import type { PendingPayment } from '../types';

interface PaymentValidationDialogProps {
  payment: PendingPayment | null;
  isOpen: boolean;
  onClose: () => void;
  onValidate: (paymentId: string, comment?: string) => Promise<void>;
  isLoading?: boolean;
}

export function PaymentValidationDialog({
  payment,
  isOpen,
  onClose,
  onValidate,
  isLoading = false,
}: PaymentValidationDialogProps) {
  const [comment, setComment] = useState('');

  const handleValidate = async () => {
    if (!payment) return;
    await onValidate(payment.id, comment || undefined);
    setComment('');
    onClose();
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('es-GQ', {
      style: 'currency',
      currency: 'XAF',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-500" />
            Validar Pago
          </DialogTitle>
          <DialogDescription>
            Confirme la validacion del pago. Se generara un recibo automaticamente.
          </DialogDescription>
        </DialogHeader>

        {payment && (
          <div className="space-y-4 py-4">
            {/* Payment Summary */}
            <div className="bg-muted/50 p-4 rounded-lg space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Referencia:</span>
                <span className="font-mono">{payment.paymentReference}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Monto:</span>
                <span className="font-bold text-lg">
                  {formatCurrency(payment.totalAmount)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Metodo:</span>
                <span className="capitalize">{payment.paymentMethod?.replace('_', ' ') || 'N/A'}</span>
              </div>
              {payment.userName && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Ciudadano:</span>
                  <span>{payment.userName}</span>
                </div>
              )}
            </div>

            {/* Comment */}
            <div className="space-y-2">
              <Label htmlFor="comment">Comentario (opcional)</Label>
              <Textarea
                id="comment"
                placeholder="Agregar comentario de validacion..."
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancelar
          </Button>
          <Button
            onClick={handleValidate}
            disabled={isLoading || !payment}
            className="bg-green-600 hover:bg-green-700"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Validando...
              </>
            ) : (
              <>
                <CheckCircle className="mr-2 h-4 w-4" />
                Validar Pago
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PaymentValidationDialog;
