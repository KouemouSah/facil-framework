'use client';

/**
 * Dialog for verification/rejection confirmation
 * Includes confirmation checkbox, notes field, and fraud option for rejection
 */

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
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertTriangle, CheckCircle, XCircle, Shield } from 'lucide-react';
import type { ExtractedIdentifier } from '../types';

interface VerificationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: 'verify' | 'reject' | 'verify-batch';
  identifier?: ExtractedIdentifier;
  identifiers?: ExtractedIdentifier[];
  onConfirm: (data: {
    notes?: string;
    isFraud?: boolean;
    reason?: string;
  }) => void;
  isLoading?: boolean;
}

const identifierTypeLabels: Record<string, string> = {
  dni: 'DNI',
  pasaporte: 'Pasaporte',
  permiso_residencia: 'Permiso de Residencia',
  certificado_conducir: 'Certificado de Conducir',
  registro_civil: 'Registro Civil',
};

export function VerificationDialog({
  open,
  onOpenChange,
  mode,
  identifier,
  identifiers = [],
  onConfirm,
  isLoading = false,
}: VerificationDialogProps) {
  const [confirmed, setConfirmed] = useState(false);
  const [notes, setNotes] = useState('');
  const [reason, setReason] = useState('');
  const [isFraud, setIsFraud] = useState(false);

  const isVerify = mode === 'verify' || mode === 'verify-batch';
  const isBatch = mode === 'verify-batch';
  const isReject = mode === 'reject';

  const handleConfirm = () => {
    if (isVerify) {
      onConfirm({ notes: notes || undefined });
    } else {
      onConfirm({
        reason,
        isFraud,
      });
    }
    // Reset state
    setConfirmed(false);
    setNotes('');
    setReason('');
    setIsFraud(false);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      // Reset state when closing
      setConfirmed(false);
      setNotes('');
      setReason('');
      setIsFraud(false);
    }
    onOpenChange(open);
  };

  const canConfirm = isVerify
    ? confirmed
    : confirmed && reason.length >= 5;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {isVerify ? (
              <>
                <CheckCircle className="h-5 w-5 text-green-600" />
                {isBatch
                  ? 'Validar todos los identificadores'
                  : 'Confirmar validación'}
              </>
            ) : (
              <>
                <XCircle className="h-5 w-5 text-red-600" />
                Rechazar identificador
              </>
            )}
          </DialogTitle>
          <DialogDescription>
            {isVerify
              ? 'Esta acción registrará el identificador en el cache para verificaciones futuras.'
              : 'Esta acción marcará el identificador como rechazado.'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Identifier summary */}
          {identifier && !isBatch && (
            <div className="rounded-lg border p-3 bg-muted/50">
              <p className="text-sm font-medium">
                {identifierTypeLabels[identifier.identifierType] ||
                  identifier.identifierType}
              </p>
              <p className="text-lg font-mono font-semibold">
                {identifier.value}
              </p>
              <p className="text-sm text-muted-foreground">
                Documento: {identifier.documentName}
              </p>
            </div>
          )}

          {/* Batch summary */}
          {isBatch && identifiers.length > 0 && (
            <div className="rounded-lg border p-3 bg-muted/50">
              <p className="text-sm font-medium mb-2">
                Identificadores a validar ({identifiers.length}):
              </p>
              <ul className="space-y-1 text-sm">
                {identifiers.map((id, idx) => (
                  <li key={idx} className="flex justify-between">
                    <span>
                      {identifierTypeLabels[id.identifierType] ||
                        id.identifierType}
                    </span>
                    <span className="font-mono">{id.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Confirmation checkbox */}
          <div className="flex items-start space-x-3">
            <Checkbox
              id="confirmed"
              checked={confirmed}
              onCheckedChange={(checked) => setConfirmed(checked === true)}
            />
            <div className="grid gap-1.5 leading-none">
              <Label
                htmlFor="confirmed"
                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {isVerify
                  ? 'He verificado este identificador con la fuente externa'
                  : 'Confirmo el rechazo de este identificador'}
              </Label>
              <p className="text-sm text-muted-foreground">
                {isVerify
                  ? 'El número ha sido confirmado como válido (via CNEDOGE, llamada, etc.)'
                  : 'El identificador no es válido o no corresponde al solicitante'}
              </p>
            </div>
          </div>

          {/* Notes field for verification */}
          {isVerify && (
            <div className="space-y-2">
              <Label htmlFor="notes">Notas (opcional)</Label>
              <Textarea
                id="notes"
                placeholder="Ej: Verificado por llamada a CNEDOGE..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={500}
                rows={2}
              />
            </div>
          )}

          {/* Reason field for rejection */}
          {isReject && (
            <div className="space-y-2">
              <Label htmlFor="reason">
                Motivo del rechazo <span className="text-red-500">*</span>
              </Label>
              <Textarea
                id="reason"
                placeholder="Ej: Documento parece alterado, número no existe en el sistema..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                maxLength={500}
                rows={3}
                required
              />
              <p className="text-xs text-muted-foreground">
                Mínimo 5 caracteres
              </p>
            </div>
          )}

          {/* Fraud checkbox for rejection */}
          {isReject && (
            <div className="space-y-3">
              <div className="flex items-start space-x-3">
                <Checkbox
                  id="fraud"
                  checked={isFraud}
                  onCheckedChange={(checked) => setIsFraud(checked === true)}
                />
                <div className="grid gap-1.5 leading-none">
                  <Label
                    htmlFor="fraud"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 flex items-center gap-1.5"
                  >
                    <Shield className="h-4 w-4 text-red-600" />
                    Marcar como fraude
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Bloquea este número para uso futuro (is_active=false)
                  </p>
                </div>
              </div>

              {isFraud && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    Este identificador será bloqueado permanentemente. Las
                    futuras solicitudes con este número serán rechazadas
                    automáticamente.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isLoading}
          >
            Cancelar
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={!canConfirm || isLoading}
            variant={isReject ? 'destructive' : 'default'}
            className={isVerify ? 'bg-green-600 hover:bg-green-700' : ''}
          >
            {isLoading ? (
              'Procesando...'
            ) : isVerify ? (
              <>
                <CheckCircle className="h-4 w-4 mr-1.5" />
                {isBatch ? 'Validar todos' : 'Validar'}
              </>
            ) : (
              <>
                <XCircle className="h-4 w-4 mr-1.5" />
                Rechazar
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
