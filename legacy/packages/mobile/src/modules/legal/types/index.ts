/**
 * Types for the Legal module — mirrors backend `legal_routes.py` schemas.
 *
 * Generated from `app/modules/legal/api/legal_routes.py` (Phase 10/B).
 */

export interface LegalVersionsResponse {
  privacy_version: string;
  privacy_last_updated: string; // ISO date YYYY-MM-DD
  terms_version: string;
  terms_last_updated: string;
  cookies_version: string;
  cookies_last_updated: string;
}

export interface LegalAcceptPayload {
  terms_version: string;
  privacy_version: string;
}

export interface LegalAcceptResponse {
  status: 'accepted';
  terms_accepted_at: string; // ISO datetime
  privacy_accepted_at: string;
}

/**
 * Backend error shape for stale-version (HTTP 400). Used by mobile to show
 * "Please update the app" guidance and force a refetch of /legal/versions.
 */
export interface LegalStaleVersionError {
  error: 'outdated_terms_version' | 'outdated_privacy_version';
  expected: string;
  received: string;
}

/**
 * Backend error shape when the role is exempt (HTTP 403). Should never reach
 * mobile UI — mobile only shows the acceptance screen for citizen/business/
 * accountant roles in the first place.
 */
export interface LegalRoleExemptError {
  error: 'legal_acceptance_not_required_for_role';
  role: string;
  message: string;
}
