/**
 * Hook for fetching unreconciled bank transactions
 *
 * @module treasury/hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';
import { useTranslations } from 'next-intl';
import { treasuryApi } from '../services/api';
import { RECONCILIATION_SUGGESTIONS_KEY } from './useReconciliationSuggestions';
import type {
  BankTransactionParams,
  BankTransactionListResponse,
  ReconcileRequest,
  BankTransaction,
} from '../types';

export const UNRECONCILED_QUERY_KEY = 'treasury-unreconciled-transactions';

export function useUnreconciledTransactions(params: BankTransactionParams = {}) {
  return useQuery<BankTransactionListResponse, Error>({
    queryKey: [UNRECONCILED_QUERY_KEY, params],
    queryFn: () => treasuryApi.getUnreconciledTransactions(params),
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 60 * 1000, // Auto-refresh every minute
    retry: 2,
  });
}

export function useReconcileTransaction() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const t = useTranslations('treasury');

  return useMutation<BankTransaction, Error, ReconcileRequest>({
    mutationFn: (request) => treasuryApi.reconcileTransaction(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [UNRECONCILED_QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [RECONCILIATION_SUGGESTIONS_KEY] });
      toast({
        title: t('reconciliationPage.toast.reconcileSuccess'),
        description: t('reconciliationPage.toast.reconcileSuccessDesc'),
      });
    },
    onError: () => {
      toast({
        variant: 'destructive',
        title: t('reconciliationPage.toast.reconcileError'),
        description: t('reconciliationPage.toast.reconcileErrorDesc'),
      });
    },
  });
}

export default useUnreconciledTransactions;
