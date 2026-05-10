/**
 * Company archive lifecycle hooks (web).
 *
 * Wired on the soft-delete endpoints introduced by migration 314 + Phase 1
 * backend (see `.claude/plans/SOFT_DELETE_COMPANIES_PLAN.md`).
 *
 *   POST   /api/v1/companies/{id}/archive    — citizen, owner-only
 *   POST   /api/v1/companies/{id}/unarchive  — admin, requires company.unarchive
 *   DELETE /api/v1/companies/{id}            — admin, requires company.hard_delete
 *
 * Companion to {@link useCompanyMembership}, which derives whether the
 * current user is allowed to invoke the citizen archive flow.
 *
 * Mirrors the mobile `useCompanyMembership` hook
 * (`packages/mobile/src/modules/companies/services/companies-hooks.ts`) so
 * the web and mobile surfaces share a single mental model of role-based
 * gating, even though only mobile/web ARCHIVE is exposed today.
 */

'use client'

import { useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import { toast } from 'sonner'

import { companiesApi } from '../services/api'
import { companyMembersKeys, useCompanyMembers } from './useCompanyMembers'
import type { CompanyMember, CompanyMemberRole } from '../types'

// =============================================================================
// QUERY KEYS
// =============================================================================

export const companyDetailKeys = {
  all: ['companies'] as const,
  detail: (id: string) => [...companyDetailKeys.all, 'detail', id] as const,
}

// =============================================================================
// useCompanyMembership — derived role + permissions
// =============================================================================

/**
 * Resolves the current user's membership inside a company and exposes
 * role-derived permission flags. Mirrors the backend authorisation contract
 * exactly so UI gating cannot drift from server-side checks.
 *
 *   PUT  /companies/{id}        -> company_owner | company_admin
 *   POST /{id}/archive          -> company_owner only (citizen surface)
 *   POST /{id}/members          -> company_owner | company_admin
 *   POST /{id}/unarchive        -> admin permission (NOT exposed here)
 *   DELETE /{id}                -> admin permission (NOT exposed here)
 *
 * NOTE: The citizen surface in `/empresas/[companyId]` does NOT yet expose
 * Edit. We ship `canEdit` for symmetry with mobile and for the day backend
 * grows the safety net.
 */
export interface CompanyMembershipPermissions {
  membership: CompanyMember | null
  isOwner: boolean
  isAdmin: boolean
  canEdit: boolean
  canArchive: boolean
  canManageMembers: boolean
}

export function useCompanyMembership(
  companyId: string | null | undefined,
  currentUserId: string | null | undefined,
): CompanyMembershipPermissions {
  const members = useCompanyMembers(companyId ?? '')

  return useMemo<CompanyMembershipPermissions>(() => {
    const membership =
      (members.data ?? []).find((m: CompanyMember) => m.user_id === currentUserId) ?? null
    const role: CompanyMemberRole | undefined = membership?.role
    const isOwner = role === 'company_owner'
    const isAdmin = role === 'company_admin'
    return {
      membership,
      isOwner,
      isAdmin,
      canEdit: isOwner || isAdmin,
      canArchive: isOwner,
      canManageMembers: isOwner || isAdmin,
    }
  }, [members.data, currentUserId])
}

// =============================================================================
// Mutations
// =============================================================================

/**
 * Type of the structured 409 payload returned by POST /archive when the
 * company still has active dependencies.
 */
export interface ArchiveBlockers {
  active_licenses: number
  pending_payments: number
  open_requests: number
  active_inspections: number
}

/** True if the AxiosError describes the structured 409 blocker response. */
export function isArchiveBlockedError(
  err: unknown,
): err is AxiosError<{ detail: { message: string; blockers: ArchiveBlockers } }> {
  if (!err || typeof err !== 'object') return false
  const e = err as AxiosError<{ detail: { blockers?: unknown } }>
  if (e.response?.status !== 409) return false
  const detail = e.response?.data?.detail
  return (
    typeof detail === 'object'
    && detail !== null
    && 'blockers' in detail
  )
}

/**
 * Archive a company — citizen surface.
 *
 * Caller is responsible for surfacing the structured 409 blocker payload to
 * the user (use {@link isArchiveBlockedError} to type-guard the error and
 * read `err.response.data.detail.blockers`).
 */
export function useArchiveCompany() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (companyId: string) => companiesApi.archive(companyId),
    onSuccess: (_data, companyId) => {
      // Invalidate caches so the company drops off the user's listings.
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.detail(companyId) })
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.all })
      queryClient.invalidateQueries({ queryKey: companyMembersKeys.list(companyId) })
      toast.success('Empresa archivada')
    },
    onError: (err: unknown) => {
      // Don't toast on 409 — the caller renders a dedicated dialog with the
      // blockers list; a generic toast would be misleading.
      if (isArchiveBlockedError(err)) return
      toast.error('No se pudo archivar la empresa', {
        description: err instanceof Error ? err.message : 'Error desconocido',
      })
    },
  })
}

/** Restore an archived company (admin tooling). */
export function useUnarchiveCompany() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (companyId: string) => companiesApi.unarchive(companyId),
    onSuccess: (_data, companyId) => {
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.detail(companyId) })
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.all })
      toast.success('Empresa restaurada')
    },
    onError: (err: unknown) => {
      toast.error('No se pudo restaurar la empresa', {
        description: err instanceof Error ? err.message : 'Error desconocido',
      })
    },
  })
}

/**
 * Hard-delete an archived company (admin tooling, post-archive only).
 *
 * The backend re-checks blockers and rejects with 409 if the archive grew
 * dependencies in the meantime. Surface the same dialog as for archive.
 */
export function useHardDeleteCompany() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (companyId: string) => companiesApi.hardDelete(companyId),
    onSuccess: (_data, companyId) => {
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.detail(companyId) })
      queryClient.invalidateQueries({ queryKey: companyDetailKeys.all })
      toast.success('Empresa eliminada definitivamente')
    },
    onError: (err: unknown) => {
      if (isArchiveBlockedError(err)) return
      toast.error('No se pudo eliminar la empresa', {
        description: err instanceof Error ? err.message : 'Error desconocido',
      })
    },
  })
}

/**
 * Read the blockers payload out of an AxiosError. Returns null if the error
 * is not the structured 409. Convenience helper for UI consumers.
 */
export function getArchiveBlockers(err: unknown): ArchiveBlockers | null {
  if (!isArchiveBlockedError(err)) return null
  return err.response?.data.detail.blockers ?? null
}
