/**
 * Hook for bank configurations
 *
 * @module treasury/hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { treasuryApi } from '../services/api';
import type {
  BankConfiguration,
  BankConfigurationCreate,
  BankConfigurationUpdate,
} from '../types';

export const BANK_CONFIGS_QUERY_KEY = 'treasury-bank-configurations';

export function useBankConfigurations(activeOnly: boolean = false) {
  return useQuery<BankConfiguration[], Error>({
    queryKey: [BANK_CONFIGS_QUERY_KEY, activeOnly],
    queryFn: () => treasuryApi.getBankConfigurations(activeOnly),
    staleTime: 5 * 60 * 1000, // 5 minutes - configs don't change often
    retry: 2,
  });
}

export function useCreateBankConfiguration() {
  const queryClient = useQueryClient();

  return useMutation<BankConfiguration, Error, BankConfigurationCreate>({
    mutationFn: (config) => treasuryApi.createBankConfiguration(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [BANK_CONFIGS_QUERY_KEY] });
    },
  });
}

export function useUpdateBankConfiguration() {
  const queryClient = useQueryClient();

  return useMutation<
    BankConfiguration,
    Error,
    { configId: number; update: BankConfigurationUpdate }
  >({
    mutationFn: ({ configId, update }) =>
      treasuryApi.updateBankConfiguration(configId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [BANK_CONFIGS_QUERY_KEY] });
    },
  });
}

export default useBankConfigurations;
