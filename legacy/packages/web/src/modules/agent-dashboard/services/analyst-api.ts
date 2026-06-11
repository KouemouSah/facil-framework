/**
 * Unified Analyst API Service
 * Calls POST /api/v1/agents/analyst/ask (Phase 3 unified endpoint)
 *
 * Used by SupervisorAssistantTab. The backend resolves agent_type
 * automatically from the user's agent_profile + entity.
 *
 * @module agent-dashboard/services/analyst-api
 */

import { fetchClient } from '@/core/api';

// ── Types ────────────────────────────────────────────────────────────────────

export interface AnalystAskRequest {
  question: string;
  previous_context?: {
    question: string;
    tools_used: string[];
  };
  session_id?: string;
}

export interface AnalystAskResponse {
  answer: string;
  tools_used: string[];
  data: Record<string, unknown>;
  artifacts?: Array<Record<string, unknown>>;
  agent_type?: string;
}

export interface AnalystBriefingResponse {
  briefing: string;
  priority: string;
  recommendations?: string[];
  agent_type?: string;
}

// ── API ──────────────────────────────────────────────────────────────────────

const ANALYST_BASE = '/agents/analyst';

export const analystApi = {
  /**
   * Ask the unified analyst endpoint.
   * Backend resolves agent_type from user profile.
   */
  ask: async (
    question: string,
    previousContext?: { question: string; tools_used: string[] },
    sessionId?: string,
  ): Promise<AnalystAskResponse> => {
    const body: AnalystAskRequest = { question };
    if (previousContext) {
      body.previous_context = previousContext;
    }
    if (sessionId) {
      body.session_id = sessionId;
    }
    return fetchClient.post<AnalystAskResponse>(`${ANALYST_BASE}/ask`, body);
  },

  /**
   * Get analyst briefing (currently treasury only).
   */
  getBriefing: async (): Promise<AnalystBriefingResponse> => {
    return fetchClient.get<AnalystBriefingResponse>(`${ANALYST_BASE}/briefing`);
  },
};

export default analystApi;
