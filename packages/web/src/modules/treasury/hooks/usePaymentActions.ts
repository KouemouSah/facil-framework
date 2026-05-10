/**
 * Hook for payment actions (validate, reject) - single and batch
 * Includes error handling with user-friendly toast messages
 *
 * @module treasury/hooks
 * @version 3.0.0 - Added batch actions support
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useToast } from '@/hooks/use-toast';
import { treasuryApi } from '../services/api';
import type {
  PaymentValidationRequest,
  PaymentRejectionRequest,
  PaymentActionResponse,
} from '../types';
import { getTreasuryErrorCode } from '../types';
import { PENDING_PAYMENTS_QUERY_KEY } from './usePendingPayments';

interface BatchResult {
  success: string[];
  failed: Array<{ id: string; error: string }>;
}

export function usePaymentActions() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const tTreasury = useTranslations('treasury');
  const tCommon = useTranslations('common');

  const invalidatePayments = () => {
    queryClient.invalidateQueries({ queryKey: [PENDING_PAYMENTS_QUERY_KEY] });
  };

  /**
   * Get translated error message from API error
   */
  const getTranslatedError = (error: unknown, fallbackKey: string): string => {
    const errorCode = getTreasuryErrorCode(error);
    if (errorCode) {
      try {
        return tTreasury(`errors.${errorCode}`);
      } catch {
        // Fall through to fallback
      }
    }
    try {
      return tTreasury(`errors.${fallbackKey}`);
    } catch {
      return tTreasury('errors.generic');
    }
  };

  const showError = (error: unknown, fallbackKey: string) => {
    const message = getTranslatedError(error, fallbackKey);
    toast({
      title: tCommon('error'),
      description: message,
      variant: 'destructive',
    });
  };

  const showSuccess = (message: string) => {
    toast({
      title: tCommon('success'),
      description: message,
    });
  };

  // Single payment validation
  const validatePayment = useMutation<
    PaymentActionResponse,
    Error,
    { paymentId: string; request?: PaymentValidationRequest }
  >({
    mutationFn: ({ paymentId, request }) =>
      treasuryApi.validatePayment(paymentId, request),
    onSuccess: (data) => {
      invalidatePayments();
      // Check if backend returned success=false (partial failure)
      if (data.success === false) {
        toast({
          title: tCommon('error'),
          description: data.error || data.messageEs || 'Error al validar el pago',
          variant: 'destructive',
        });
        return;
      }
      if (data.messageEs) {
        showSuccess(data.messageEs);
      } else {
        showSuccess('Pago validado correctamente');
      }
    },
    onError: (error) => {
      showError(error, 'validateFailed');
    },
  });

  // Single payment rejection
  const rejectPayment = useMutation<
    PaymentActionResponse,
    Error,
    { paymentId: string; request: PaymentRejectionRequest }
  >({
    mutationFn: ({ paymentId, request }) =>
      treasuryApi.rejectPayment(paymentId, request),
    onSuccess: (data) => {
      invalidatePayments();
      // Check if backend returned success=false (partial failure)
      if (data.success === false) {
        toast({
          title: tCommon('error'),
          description: data.error || data.messageEs || 'Error al rechazar el pago',
          variant: 'destructive',
        });
        return;
      }
      if (data.messageEs) {
        showSuccess(data.messageEs);
      } else {
        showSuccess('Pago rechazado correctamente');
      }
    },
    onError: (error) => {
      showError(error, 'rejectFailed');
    },
  });

  // Batch validation
  const validateBatch = useMutation<
    BatchResult,
    Error,
    { paymentIds: string[]; comment?: string }
  >({
    mutationFn: async ({ paymentIds, comment }) => {
      const results: BatchResult = { success: [], failed: [] };

      // Process sequentially to avoid overwhelming the server
      for (const paymentId of paymentIds) {
        try {
          const response = await treasuryApi.validatePayment(paymentId, comment ? { comment } : undefined);
          // Check backend response success field
          if (response.success === false) {
            results.failed.push({
              id: paymentId,
              error: response.error || 'Error de validacion',
            });
          } else {
            results.success.push(paymentId);
          }
        } catch (error) {
          results.failed.push({
            id: paymentId,
            error: error instanceof Error ? error.message : 'Error desconocido',
          });
        }
      }

      return results;
    },
    onSuccess: (results) => {
      invalidatePayments();
      if (results.success.length > 0) {
        toast({
          title: 'Validacion completada',
          description: `${results.success.length} pago(s) validado(s) correctamente.${
            results.failed.length > 0
              ? ` ${results.failed.length} fallido(s).`
              : ''
          }`,
          variant: results.failed.length > 0 ? 'default' : 'default',
        });
      }
      if (results.failed.length > 0 && results.success.length === 0) {
        toast({
          title: 'Error en validacion',
          description: `No se pudo validar ningun pago. ${results.failed.length} error(es).`,
          variant: 'destructive',
        });
      }
    },
    onError: (error) => {
      showError(error, 'validateFailed');
    },
  });

  // Batch rejection
  const rejectBatch = useMutation<
    BatchResult,
    Error,
    { paymentIds: string[]; reason: string }
  >({
    mutationFn: async ({ paymentIds, reason }) => {
      const results: BatchResult = { success: [], failed: [] };

      for (const paymentId of paymentIds) {
        try {
          const response = await treasuryApi.rejectPayment(paymentId, { reason });
          // Check backend response success field
          if (response.success === false) {
            results.failed.push({
              id: paymentId,
              error: response.error || 'Error de rechazo',
            });
          } else {
            results.success.push(paymentId);
          }
        } catch (error) {
          results.failed.push({
            id: paymentId,
            error: error instanceof Error ? error.message : 'Error desconocido',
          });
        }
      }

      return results;
    },
    onSuccess: (results) => {
      invalidatePayments();
      if (results.success.length > 0) {
        toast({
          title: 'Rechazo completado',
          description: `${results.success.length} pago(s) rechazado(s).${
            results.failed.length > 0
              ? ` ${results.failed.length} fallido(s).`
              : ''
          }`,
          variant: results.failed.length > 0 ? 'default' : 'default',
        });
      }
      if (results.failed.length > 0 && results.success.length === 0) {
        toast({
          title: 'Error en rechazo',
          description: `No se pudo rechazar ningun pago. ${results.failed.length} error(es).`,
          variant: 'destructive',
        });
      }
    },
    onError: (error) => {
      showError(error, 'rejectFailed');
    },
  });

  // Escalate payment to supervisor
  const escalatePayment = useMutation<
    PaymentActionResponse,
    Error,
    { paymentId: string; reason: string; level?: string }
  >({
    mutationFn: ({ paymentId, reason, level }) =>
      treasuryApi.escalatePayment(paymentId, { reason, level }),
    onSuccess: (data) => {
      invalidatePayments();
      if (data.success === false) {
        toast({
          title: tCommon('error'),
          description: data.error || data.messageEs || 'Error al escalar el pago',
          variant: 'destructive',
        });
        return;
      }
      showSuccess(data.messageEs || tTreasury('escalation.success'));
    },
    onError: (error) => {
      showError(error, 'escalateFailed');
    },
  });

  // Validate all payments in a batch
  const validateBatchPayments = useMutation<
    { success: boolean; paymentsValidated: number; batchReference?: string; error?: string },
    Error,
    { batchId: string; comment?: string }
  >({
    mutationFn: ({ batchId, comment }) =>
      treasuryApi.validateBatchPayments(batchId, comment),
    onSuccess: (data) => {
      invalidatePayments();
      if (!data.success) {
        toast({
          title: tCommon('error'),
          description: data.error || 'Error al validar el lote',
          variant: 'destructive',
        });
        return;
      }
      showSuccess(
        tTreasury('batch.validateSuccess', {
          count: data.paymentsValidated,
          reference: data.batchReference || '',
        })
      );
    },
    onError: (error) => {
      showError(error, 'validateFailed');
    },
  });

  // Reassign payment (supervisor only)
  const reassignPayment = useMutation<
    { success: boolean; targetAgentName: string },
    Error,
    { paymentId: string; targetAgentProfileId: string; reason?: string }
  >({
    mutationFn: ({ paymentId, targetAgentProfileId, reason }) =>
      treasuryApi.reassignPayment(paymentId, targetAgentProfileId, reason),
    onSuccess: (data) => {
      invalidatePayments();
      showSuccess(tTreasury('validationPage.reassignSuccess', { agent: data.targetAgentName }));
    },
    onError: (error) => {
      showError(error, 'reassignFailed');
    },
  });

  return {
    // Single actions
    validatePayment,
    rejectPayment,
    escalatePayment,
    reassignPayment,
    isValidating: validatePayment.isPending,
    isRejecting: rejectPayment.isPending,
    isEscalating: escalatePayment.isPending,
    isReassigning: reassignPayment.isPending,
    // Batch actions
    validateBatch,
    rejectBatch,
    validateBatchPayments,
    isValidatingBatch: validateBatch.isPending,
    isRejectingBatch: rejectBatch.isPending,
    isBatchProcessing: validateBatch.isPending || rejectBatch.isPending,
  };
}

export default usePaymentActions;
