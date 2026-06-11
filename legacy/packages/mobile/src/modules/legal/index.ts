/**
 * Legal module — Privacy Policy + Terms of Service flows.
 *
 * Phase 10/B (2026-05-02). See:
 *  - .claude/plans/MOBILE_PHASE_10_B_LEGAL_DETAILED.md
 *  - packages/backend/app/modules/legal/api/legal_routes.py
 */

export { useLegalVersions } from './hooks/use-legal-versions';
export { useAcceptLegal } from './hooks/use-accept-legal';
export { LegalAcceptanceCard } from './components/legal-acceptance-card';
export type {
  LegalVersionsResponse,
  LegalAcceptPayload,
  LegalAcceptResponse,
  LegalStaleVersionError,
  LegalRoleExemptError,
} from './types';
