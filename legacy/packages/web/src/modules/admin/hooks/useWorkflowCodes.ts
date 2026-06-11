/**
 * Workflow Codes Hook
 * React Query hook for fetching available workflow codes (dropdown selection)
 *
 * @module admin/hooks
 * @date 2026-02-02
 *
 * USAGE:
 * - useWorkflowCodes(): Get flat list of all workflow codes
 * - useWorkflowCodesGrouped(): Get workflows grouped by category for Select components
 */

'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { menuConfigApi } from '../services/menuConfigService';
import type { WorkflowCode, SampleRequest } from '../services/menuConfigService';

// =============================================================================
// QUERY KEYS
// =============================================================================

export const workflowCodesKeys = {
  all: ['workflow-codes'] as const,
  list: () => [...workflowCodesKeys.all, 'list'] as const,
  sample: (workflowCode: string) => [...workflowCodesKeys.all, 'sample', workflowCode] as const,
};

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Hook to fetch all available workflow codes
 * Used for dropdown selection in display config forms
 */
export function useWorkflowCodes() {
  return useQuery({
    queryKey: workflowCodesKeys.list(),
    queryFn: async () => {
      const response = await menuConfigApi.getWorkflowCodes();
      return response.items;
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - workflows don't change often
  });
}

/**
 * Hook to fetch workflows grouped by category
 * Useful for grouped Select/dropdown components
 */
export function useWorkflowCodesGrouped() {
  const { data: workflows, ...rest } = useWorkflowCodes();

  const grouped = useMemo(() => {
    if (!workflows) return {};

    return workflows.reduce(
      (acc, wf) => {
        const category = wf.category || 'Otros';
        if (!acc[category]) acc[category] = [];
        acc[category].push(wf);
        return acc;
      },
      {} as Record<string, WorkflowCode[]>
    );
  }, [workflows]);

  // Get sorted category names for consistent ordering
  const categories = useMemo(() => {
    return Object.keys(grouped).sort((a, b) => {
      // Put "Otros" at the end
      if (a === 'Otros') return 1;
      if (b === 'Otros') return -1;
      return a.localeCompare(b);
    });
  }, [grouped]);

  return {
    grouped,
    categories,
    workflows,
    ...rest,
  };
}

/**
 * Hook to fetch a sample service request for preview
 * Shows real data in the display config form preview
 */
export function useSampleRequest(workflowCode: string | undefined) {
  return useQuery<SampleRequest | null>({
    queryKey: workflowCodesKeys.sample(workflowCode || ''),
    queryFn: async () => {
      if (!workflowCode) return null;
      return menuConfigApi.getSampleRequest(workflowCode);
    },
    enabled: !!workflowCode,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
