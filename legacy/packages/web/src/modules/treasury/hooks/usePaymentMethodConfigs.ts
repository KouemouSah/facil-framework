/**
 * Payment Method Configurations Hook
 * React Query hooks for payment method CRUD operations
 *
 * @module treasury/hooks
 */

'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { treasuryApi } from '../services';
import type {
  PaymentMethodConfig,
  PaymentMethodConfigCreate,
  PaymentMethodConfigUpdate,
  PaymentMethodReorderRequest,
} from '../types';

const QUERY_KEY = 'payment-method-configs';

/**
 * Hook to fetch all payment method configurations
 */
export function usePaymentMethodConfigs(activeOnly: boolean = false) {
  return useQuery<PaymentMethodConfig[], Error>({
    queryKey: [QUERY_KEY, { activeOnly }],
    queryFn: () => treasuryApi.getPaymentMethods(activeOnly),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch single payment method configuration
 */
export function usePaymentMethodConfig(code: string | null) {
  return useQuery<PaymentMethodConfig, Error>({
    queryKey: [QUERY_KEY, code],
    queryFn: () => treasuryApi.getPaymentMethod(code!),
    enabled: !!code,
  });
}

/**
 * Hook to create a new payment method configuration
 */
export function useCreatePaymentMethod() {
  const queryClient = useQueryClient();

  return useMutation<PaymentMethodConfig, Error, PaymentMethodConfigCreate>({
    mutationFn: (config) => treasuryApi.createPaymentMethod(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

/**
 * Hook to update a payment method configuration
 */
export function useUpdatePaymentMethod() {
  const queryClient = useQueryClient();

  return useMutation<
    PaymentMethodConfig,
    Error,
    { code: string; update: PaymentMethodConfigUpdate }
  >({
    mutationFn: ({ code, update }) => treasuryApi.updatePaymentMethod(code, update),
    onSuccess: (_, { code }) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, code] });
    },
  });
}

/**
 * Hook to delete a payment method configuration
 */
export function useDeletePaymentMethod() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (code) => treasuryApi.deletePaymentMethod(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

/**
 * Hook to reorder payment methods
 */
export function useReorderPaymentMethods() {
  const queryClient = useQueryClient();

  return useMutation<PaymentMethodConfig[], Error, PaymentMethodReorderRequest>({
    mutationFn: (request) => treasuryApi.reorderPaymentMethods(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

/**
 * Hook to toggle payment method active status
 */
export function useTogglePaymentMethodActive() {
  const queryClient = useQueryClient();

  return useMutation<PaymentMethodConfig, Error, { code: string; isActive: boolean }>({
    mutationFn: ({ code, isActive }) =>
      treasuryApi.updatePaymentMethod(code, { isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}
