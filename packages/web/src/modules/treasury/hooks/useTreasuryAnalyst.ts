'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import treasuryApi from '../services/api';

export const TREASURY_BRIEFING_QUERY_KEY = 'treasury-analyst-briefing';

export interface AnalystMutationParams {
  question: string;
  previousContext?: { question: string; toolsUsed: string[] };
  sessionId?: string;
}

/**
 * Mutation hook for treasury analyst Q&A.
 * Sends a question (+ optional previous context for drill-down + session_id for memory).
 */
export function useTreasuryAnalyst() {
  return useMutation({
    mutationFn: (params: AnalystMutationParams) =>
      treasuryApi.askAnalyst(params.question, params.previousContext, params.sessionId),
  });
}

/**
 * Query hook for auto-briefing.
 * Fetches pre-computed financial briefing with priority.
 */
export function useTreasuryBriefing() {
  return useQuery({
    queryKey: [TREASURY_BRIEFING_QUERY_KEY],
    queryFn: () => treasuryApi.getAnalystBriefing(),
    staleTime: 5 * 60 * 1000, // 5 min
    refetchInterval: 5 * 60 * 1000,
  });
}
