/**
 * Hook for verification actions (verify, verify-batch, reject)
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { verifyIdentifier, verifyBatch, rejectIdentifier } from '../services/api';
import type {
  VerifyIdentifierRequest,
  VerifyIdentifierResponse,
  VerifyBatchRequest,
  VerifyBatchResponse,
  RejectIdentifierRequest,
  RejectIdentifierResponse,
} from '../types';
import { PENDING_VERIFICATIONS_KEY } from './usePendingVerifications';
import { VERIFICATION_DETAILS_KEY } from './useVerificationDetails';

interface UseVerificationActionsOptions {
  onVerifySuccess?: (response: VerifyIdentifierResponse) => void;
  onVerifyBatchSuccess?: (response: VerifyBatchResponse) => void;
  onRejectSuccess?: (response: RejectIdentifierResponse) => void;
  onError?: (error: Error) => void;
}

export function useVerificationActions(
  requestId: string,
  options: UseVerificationActionsOptions = {}
) {
  const queryClient = useQueryClient();
  const {
    onVerifySuccess,
    onVerifyBatchSuccess,
    onRejectSuccess,
    onError,
  } = options;

  // Invalidate related queries after any mutation
  const invalidateQueries = () => {
    queryClient.invalidateQueries({ queryKey: [PENDING_VERIFICATIONS_KEY] });
    queryClient.invalidateQueries({
      queryKey: [VERIFICATION_DETAILS_KEY, requestId],
    });
  };

  // Verify single identifier
  const verifyMutation = useMutation<
    VerifyIdentifierResponse,
    Error,
    VerifyIdentifierRequest
  >({
    mutationFn: (data) => verifyIdentifier(requestId, data),
    onSuccess: (response) => {
      invalidateQueries();
      onVerifySuccess?.(response);
    },
    onError,
  });

  // Verify batch (all pending)
  const verifyBatchMutation = useMutation<
    VerifyBatchResponse,
    Error,
    VerifyBatchRequest
  >({
    mutationFn: (data) => verifyBatch(requestId, data),
    onSuccess: (response) => {
      invalidateQueries();
      onVerifyBatchSuccess?.(response);
    },
    onError,
  });

  // Reject identifier
  const rejectMutation = useMutation<
    RejectIdentifierResponse,
    Error,
    RejectIdentifierRequest
  >({
    mutationFn: (data) => rejectIdentifier(requestId, data),
    onSuccess: (response) => {
      invalidateQueries();
      onRejectSuccess?.(response);
    },
    onError,
  });

  return {
    // Verify single
    verify: verifyMutation.mutate,
    verifyAsync: verifyMutation.mutateAsync,
    isVerifying: verifyMutation.isPending,
    verifyError: verifyMutation.error,

    // Verify batch
    verifyBatch: verifyBatchMutation.mutate,
    verifyBatchAsync: verifyBatchMutation.mutateAsync,
    isVerifyingBatch: verifyBatchMutation.isPending,
    verifyBatchError: verifyBatchMutation.error,

    // Reject
    reject: rejectMutation.mutate,
    rejectAsync: rejectMutation.mutateAsync,
    isRejecting: rejectMutation.isPending,
    rejectError: rejectMutation.error,

    // Combined loading state
    isLoading:
      verifyMutation.isPending ||
      verifyBatchMutation.isPending ||
      rejectMutation.isPending,
  };
}
