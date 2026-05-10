/**
 * useEntityAccess Hook
 * Verifies if the current agent has access to a specific entity dashboard
 *
 * @module agent-dashboard/hooks
 * @date 2026-01-18
 * @updated 2026-02-22 - Replaced hardcoded ENTITY_HIERARCHY/MINISTRY_ENTITIES with backend-derived data
 *
 * Security: Prevents unauthorized access to entity dashboards
 * An agent should only access dashboards for their assigned entity or ministry
 */

'use client';

import { useMemo } from 'react';
import { useAgentProfile } from './useAgentDashboard';
import type { EntityCode, MinistryCode } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface EntityAccessResult {
  /** Whether the agent has access to the requested entity */
  hasAccess: boolean;
  /** Whether the access check is still loading */
  isLoading: boolean;
  /** Error if any occurred during the check */
  error: Error | null;
  /** The agent's assigned entity code */
  agentEntityCode: EntityCode | null;
  /** The agent's ministry code (if ministry_agent) */
  agentMinistryCode: MinistryCode | null;
  /** Whether the agent is a supervisor */
  isSupervisor: boolean;
  /** Reason for denial (for error messages) */
  denialReason: 'not_authenticated' | 'wrong_entity' | 'no_agent_profile' | null;
  /** List of entities the agent can access */
  allowedEntities: EntityCode[];
}

// =============================================================================
// HOOK
// =============================================================================

/**
 * Check if an agent has access to a specific entity dashboard
 *
 * Access rules:
 * 1. Agent must be authenticated and have an agent profile
 * 2. Agent's entity must match the requested entity (or be a parent)
 * 3. Ministry agents can access all entities under their ministry
 * 4. Supervisors have the same entity restrictions but more permissions within
 *
 * Entity hierarchy and ministry mappings are derived from the backend profile
 * (child_entity_codes, ministry_entities) — no frontend hardcoding.
 *
 * @param requestedEntityCode - The entity dashboard being accessed
 * @returns EntityAccessResult with access decision and details
 */
export function useEntityAccess(requestedEntityCode: EntityCode): EntityAccessResult {
  const {
    data: agentProfile,
    isLoading,
    error,
  } = useAgentProfile();

  const result = useMemo<EntityAccessResult>(() => {
    // Still loading
    if (isLoading) {
      return {
        hasAccess: false,
        isLoading: true,
        error: null,
        agentEntityCode: null,
        agentMinistryCode: null,
        isSupervisor: false,
        denialReason: null,
        allowedEntities: [],
      };
    }

    // No agent profile - not authenticated as agent
    if (!agentProfile) {
      return {
        hasAccess: false,
        isLoading: false,
        error: error as Error | null,
        agentEntityCode: null,
        agentMinistryCode: null,
        isSupervisor: false,
        denialReason: 'no_agent_profile',
        allowedEntities: [],
      };
    }

    const agentEntityCode = (agentProfile.entity_code as EntityCode) || null;
    const agentMinistryCode = (agentProfile.ministry_code as MinistryCode) || null;
    const isMinistryAgent = agentProfile.agent_type === 'ministry_agent';
    const isSupervisor = agentProfile.is_supervisor;

    // Calculate allowed entities from backend-derived data
    let allowedEntities: EntityCode[] = [];

    if (isMinistryAgent && agentProfile.ministry_entities?.length) {
      // Ministry agent: backend returns all entities under the ministry
      allowedEntities = agentProfile.ministry_entities as EntityCode[];
    } else if (agentEntityCode) {
      // Entity agent: own entity + child entities from backend
      allowedEntities = [agentEntityCode];
      if (agentProfile.child_entity_codes?.length) {
        allowedEntities = [
          ...allowedEntities,
          ...(agentProfile.child_entity_codes as EntityCode[]),
        ];
      }
    }

    // Check access
    const hasAccess = allowedEntities.includes(requestedEntityCode);

    return {
      hasAccess,
      isLoading: false,
      error: null,
      agentEntityCode,
      agentMinistryCode,
      isSupervisor,
      denialReason: hasAccess ? null : 'wrong_entity',
      allowedEntities,
    };
  }, [agentProfile, isLoading, error, requestedEntityCode]);

  return result;
}

export default useEntityAccess;
