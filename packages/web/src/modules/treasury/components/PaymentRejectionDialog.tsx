/**
 * Payment Rejection Dialog
 * Modal for rejecting a payment with mandatory reason
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { XCircle, Loader2, AlertTriangle } from 'lucide-react';
import type { PendingPayment } from '../types';

interface PaymentRejectionDialogProps {
  payment: PendingPayment | null;
  isOpen: boolean;
  onClose: () => void;
  onReject: (paymentId: string, reason: string) => Promise<void>;
  isLoading?: boolean;
}

const REJECTION_REASONS = [
  { value: 'invalid_amount', label: 'Monto incorrecto' },
  { value: 'missing_documents', label: 'Documentos faltantes' },
  { value: 'duplicate_payment', label: 'Pago duplicado' },
  { value: 'invalid_reference', label: 'Referencia invalida' },
  { value: 'fraud_suspected', label: 'Sospecha de fraude' },
  { value: 'other', label: 'Otro motivo' },
];

export function PaymentRejectionDialog({
  payment,
  isOpen,
  onClose,
  onReject,
  isLoading = false,
}: PaymentRejectionDialogProps) {
  const [selectedReason, setSelectedReason] = useState('');
  const [customReason, setCustomReason] = useState('');

  const handleReject = async () => {
    if (!payment) return;

    const reason = selectedReason === 'other'
      ? customReason
      : REJECTION_REASONS.find(r => r.value === selectedReason)?.label || selectedReason;

    if (!reason.trim()) return;

    await onReject(payment.id, reason);
    setSelectedReason('');
    setCustomReason('');
    onClose();
  };

  const isValid = selectedReason && (selectedReason !== 'other' || customReason.trim());

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
          <DialogTitle className="flex items-center gap-2 text-red-600">
            <XCircle className="h-5 w-5" />
            Rechazar Pago
          </DialogTitle>
          <DialogDescription>
            Esta accion es irreversible. El ciudadano sera notificado del rechazo.
          </DialogDescription>
        </DialogHeader>

        {payment && (
          <div className="space-y-4 py-4">
            {/* Warning */}
            <div className="bg-red-50 border border-red-200 p-3 rounded-lg flex items-start gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">
                Al rechazar este pago, el ciudadano debera iniciar un nuevo proceso de pago.
              </p>
            </div>

            {/* Payment Summary */}
            <div className="bg-muted/50 p-4 rounded-lg space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Referencia:</span>
                <span className="font-mono">{payment.paymentReference}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Monto:</span>
                <span className="font-bold">{formatCurrency(payment.totalAmount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Metodo:</span>
                <span className="capitalize">{payment.paymentMethod?.replace('_', ' ') || 'N/A'}</span>
              </div>
            </div>

            {/* Reason Selection */}
            <div className="space-y-2">
              <Label htmlFor="reason">Motivo del rechazo *</Label>
              <Select value={selectedReason} onValueChange={setSelectedReason}>
                <SelectTrigger>
                  <SelectValue placeholder="Seleccione un motivo" />
                </SelectTrigger>
                <SelectContent>
                  {REJECTION_REASONS.map((reason) => (
                    <SelectItem key={reason.value} value={reason.value}>
                      {reason.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Custom Reason */}
            {selectedReason === 'other' && (
              <div className="space-y-2">
                <Label htmlFor="customReason">Especifique el motivo *</Label>
                <Textarea
                  id="customReason"
                  placeholder="Describa el motivo del rechazo..."
                  value={customReason}
                  onChange={(e) => setCustomReason(e.target.value)}
                  rows={3}
                />
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isLoading}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            onClick={handleReject}
            disabled={isLoading || !payment || !isValid}
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Rechazando...
              </>
            ) : (
              <>
                <XCircle className="mr-2 h-4 w-4" />
                Rechazar Pago
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PaymentRejectionDialog;
