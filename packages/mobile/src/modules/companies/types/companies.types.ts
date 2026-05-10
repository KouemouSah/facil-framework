/**
 * Companies feature types — re-exports from api-types + UI-only derived shapes.
 */

import type {
  AddMemberRequest,
  CompanyCreate,
  CompanyInfo,
  CompanyListResponse,
  CompanyMember,
  CompanyMemberRole,
  CompanyResponse,
  CompanySearchResult,
  CompanyUpdate,
  UpdateMemberRoleRequest,
} from '@core/api/api-types';

export type {
  AddMemberRequest,
  CompanyCreate,
  CompanyInfo,
  CompanyListResponse,
  CompanyMember,
  CompanyMemberRole,
  CompanyResponse,
  CompanySearchResult,
  CompanyUpdate,
  UpdateMemberRoleRequest,
};

// ---------------------------------------------------------------------------
// UI-only derived types
// ---------------------------------------------------------------------------

/** Roles a member can be assigned to. `company_owner` is implicit at create time
 *  and never exposed as a picker option (only one owner per company). */
export type AssignableMemberRole =
  | 'company_admin'
  | 'company_accountant'
  | 'company_member';

export const ASSIGNABLE_MEMBER_ROLES: AssignableMemberRole[] = [
  'company_admin',
  'company_accountant',
  'company_member',
];

/** Fiscal regime enum — sourced directly from the backend RegimenFiscal Pydantic enum. */
export type RegimenFiscal = 'bundle' | 'declarativo' | 'exento' | 'pendiente';

/** Form values used by the create + edit company forms (RHF + zod).
 *
 * Aligned with backend `CompanyCreate` / `CompanyUpdate` Pydantic schemas.
 * `city_name` / `provincia` are *not* editable — they appear on responses
 * via a denormalised lookup but the writable column is `city_id`. Until
 * we ship a city picker, we just don't expose them in the form.
 *
 * `representante_legal` is in `CompanyCreate` but NOT in `CompanyUpdate`.
 * Edit screens skip it from the PUT payload.
 */
export interface CompanyFormValues {
  legal_name: string;
  tax_id: string;
  representante_legal: string;
  regimen_fiscal?: RegimenFiscal | null;
  zone_id?: string | null;
  commerce_type?: string | null;
  forma_juridica?: string | null;
  sector_actividad?: string | null;
  address?: string | null;
  email?: string | null;
  phone?: string | null;
}
