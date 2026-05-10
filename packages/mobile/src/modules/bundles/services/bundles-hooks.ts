import { useQuery } from '@tanstack/react-query';
import * as api from './bundles-api';

export function useCommerceTypes() {
  return useQuery({
    queryKey: ['bundles', 'commerce-types'],
    queryFn: api.getCommerceTypes,
    staleTime: 60 * 60_000,
  });
}

export function useZones() {
  return useQuery({
    queryKey: ['bundles', 'zones'],
    queryFn: api.getZones,
    staleTime: 60 * 60_000,
  });
}

export function useSimulate(commerceType: string, zoneCode: string) {
  return useQuery({
    queryKey: ['bundles', 'simulate', commerceType, zoneCode],
    queryFn: () => api.simulate(commerceType, zoneCode),
    enabled: !!commerceType && !!zoneCode,
    staleTime: 5 * 60_000,
  });
}

// ---------------------------------------------------------------------------
// Citizen — Mes entreprises (paquete fiscal)
// ---------------------------------------------------------------------------

export function useBundleMyCompanies(fiscalYear?: number) {
  return useQuery({
    queryKey: ['bundles', 'my-companies', fiscalYear ?? 'current'],
    queryFn: () => api.getMyCompanies(fiscalYear),
    staleTime: 60_000,
  });
}

export function useBundleMyCompanyDetail(companyId: string | undefined, fiscalYear?: number) {
  return useQuery({
    queryKey: ['bundles', 'my-companies', companyId, 'detail', fiscalYear ?? 'current'],
    queryFn: () => api.getMyCompanyDetail(companyId!, fiscalYear),
    enabled: !!companyId,
    staleTime: 60_000,
  });
}

export function useBundleMyCompanyPayments(
  companyId: string | undefined,
  page = 1,
  pageSize = 20,
) {
  return useQuery({
    queryKey: ['bundles', 'my-companies', companyId, 'payments', page, pageSize],
    queryFn: () => api.getMyCompanyPayments(companyId!, page, pageSize),
    enabled: !!companyId,
    staleTime: 30_000,
  });
}
