/**
 * useUserLabels Hook
 *
 * Centralized hook for translating user roles and statuses
 * Uses hybrid approach: API for roles (real-time), static for statuses
 *
 * @module hooks
 * @author Claude Code
 * @date 2025-12-11
 */

import { useTranslations } from 'next-intl'
import { UserRole, UserStatus } from '@/types/user'
import { useEnumLabels } from './use-enum-labels'

export function useUserLabels() {
  const t = useTranslations('admin')
  const { getLabel: getEnumLabel, isLoading: isLoadingEnums } = useEnumLabels()

  /**
   * Get translated label for user role
   * Uses hybrid approach: API first (real-time), then static fallback
   */
  const getRoleLabel = (role: UserRole | string): string => {
    // Use the hybrid enum labels hook (API + fallback)
    return getEnumLabel('user_role_enum', role as string)
  }

  /**
   * Get translated label for user status
   */
  const getStatusLabel = (status: UserStatus | string): string => {
    const statusMap: Record<UserStatus, string> = {
      [UserStatus.ACTIVE]: t('users.statusActive'),
      [UserStatus.INACTIVE]: t('users.statusInactive'),
      [UserStatus.PENDING]: t('users.statusPending'),
      [UserStatus.SUSPENDED]: t('users.statusSuspended'),
    }

    return statusMap[status as UserStatus] || status
  }

  /**
   * Get all role options for filters/selects
   * Uses hybrid approach for labels (API + fallback)
   * Updated for simplified role structure (migration 048)
   */
  const getRoleOptions = (includeAll = true) => {
    const options = [
      { value: UserRole.CITIZEN, label: getRoleLabel(UserRole.CITIZEN) },
      { value: UserRole.BUSINESS, label: getRoleLabel(UserRole.BUSINESS) },
      { value: UserRole.ACCOUNTANT, label: getRoleLabel(UserRole.ACCOUNTANT) },
      { value: UserRole.FUNCIONARIO, label: getRoleLabel(UserRole.FUNCIONARIO) },
      { value: UserRole.AGENT, label: getRoleLabel(UserRole.AGENT) },
      { value: UserRole.ADMIN, label: getRoleLabel(UserRole.ADMIN) },
    ]

    if (includeAll) {
      return [{ value: 'all', label: t('users.allRoles') }, ...options]
    }
    return options
  }

  /**
   * Get all status options for filters/selects
   */
  const getStatusOptions = () => {
    return [
      { value: 'all', label: t('users.allStatuses') },
      { value: UserStatus.ACTIVE, label: getStatusLabel(UserStatus.ACTIVE) },
      { value: UserStatus.INACTIVE, label: getStatusLabel(UserStatus.INACTIVE) },
      { value: UserStatus.PENDING, label: getStatusLabel(UserStatus.PENDING) },
      { value: UserStatus.SUSPENDED, label: getStatusLabel(UserStatus.SUSPENDED) },
    ]
  }

  /**
   * Get role options grouped by category
   * Updated for simplified role structure (migration 048)
   */
  const getRoleOptionsGrouped = () => {
    return {
      citizens: [
        { value: UserRole.CITIZEN, label: getRoleLabel(UserRole.CITIZEN) },
        { value: UserRole.BUSINESS, label: getRoleLabel(UserRole.BUSINESS) },
      ],
      professionals: [
        { value: UserRole.ACCOUNTANT, label: getRoleLabel(UserRole.ACCOUNTANT) },
        { value: UserRole.FUNCIONARIO, label: getRoleLabel(UserRole.FUNCIONARIO) },
      ],
      agents: [
        { value: UserRole.AGENT, label: getRoleLabel(UserRole.AGENT) },
      ],
      admins: [{ value: UserRole.ADMIN, label: getRoleLabel(UserRole.ADMIN) }],
    }
  }

  /**
   * Get role category label
   */
  const getRoleCategoryLabel = (
    category: 'citizens' | 'professionals' | 'agents' | 'admins'
  ): string => {
    const categoryMap = {
      citizens: t('users.roleCategoryCitizens'),
      professionals: t('users.roleCategoryProfessionals'),
      agents: t('users.roleCategoryAgents'),
      admins: t('users.roleCategoryAdmins'),
    }

    return categoryMap[category]
  }

  return {
    getRoleLabel,
    getStatusLabel,
    getRoleOptions,
    getStatusOptions,
    getRoleOptionsGrouped,
    getRoleCategoryLabel,
    isLoadingRoles: isLoadingEnums,
  }
}
