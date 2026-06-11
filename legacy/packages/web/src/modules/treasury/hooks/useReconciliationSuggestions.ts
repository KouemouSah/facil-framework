'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';
import { useTranslations } from 'next-intl';
import treasuryApi from '../services/api';
import { UNRECONCILED_QUERY_KEY } from './useUnreconciledTransactions';

export const RECONCILIATION_SUGGESTIONS_KEY = 'treasury-reconciliation-suggestions';

export function useReconciliationSuggestions(limit: number = 50) {
  return useQuery({
    queryKey: [RECONCILIATION_SUGGESTIONS_KEY, limit],
    queryFn: () => treasuryApi.getReconciliationSuggestions(limit),
    staleTime: 60 * 1000, // 1 min
  });
}

export function useAutoMatch() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const t = useTranslations('treasury');

  return useMutation({
    mutationFn: (threshold: number) => treasuryApi.autoMatchReconciliation(threshold),
    onSuccess: () => {
      // C7: Invalidate BOTH queries so lists refresh
      queryClient.invalidateQueries({ queryKey: [RECONCILIATION_SUGGESTIONS_KEY] });
      queryClient.invalidateQueries({ queryKey: [UNRECONCILED_QUERY_KEY] });
    },
    onError: () => {
      toast({
        variant: 'destructive',
        title: t('reconciliationPage.toast.autoMatchError'),
        description: t('reconciliationPage.toast.autoMatchErrorDesc'),
      });
    },
  });
}
