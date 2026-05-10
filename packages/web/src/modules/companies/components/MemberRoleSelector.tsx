/**
 * Member Role Selector Component
 * Dropdown for selecting company member roles
 *
 * @module companies/components
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import * as React from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import type { CompanyMemberRole } from '../types'

// =============================================================================
// TYPES
// =============================================================================

interface MemberRoleSelectorProps {
  value: CompanyMemberRole
  onChange: (role: CompanyMemberRole) => void
  disabled?: boolean
  label?: React.ReactNode
  excludeRoles?: CompanyMemberRole[]
}

// =============================================================================
// ROLE DEFINITIONS
// =============================================================================

const ROLES: Array<{
  value: CompanyMemberRole
  label: string
  description: string
}> = [
  {
    value: 'company_owner',
    label: 'Owner',
    description: 'Full control over company, can delete and transfer ownership',
  },
  {
    value: 'company_admin',
    label: 'Admin',
    description: 'Manage members, declarations, and payments',
  },
  {
    value: 'company_accountant',
    label: 'Accountant',
    description: 'Manage declarations and payments',
  },
  {
    value: 'company_member',
    label: 'Member',
    description: 'View company and create own declarations',
  },
]

// =============================================================================
// COMPONENT
// =============================================================================

export function MemberRoleSelector({
  value,
  onChange,
  disabled = false,
  label,
  excludeRoles = [],
}: MemberRoleSelectorProps) {
  const availableRoles = ROLES.filter(
    (role) => !excludeRoles.includes(role.value)
  )

  return (
    <div className="space-y-2">
      {label && <Label htmlFor="role-select">{label}</Label>}
      <Select
        value={value}
        onValueChange={(val) => onChange(val as CompanyMemberRole)}
        disabled={disabled}
      >
        <SelectTrigger id="role-select" className="w-full">
          <SelectValue placeholder="Select a role" />
        </SelectTrigger>
        <SelectContent>
          {availableRoles.map((role) => (
            <SelectItem key={role.value} value={role.value}>
              <div className="flex flex-col">
                <span className="font-medium">{role.label}</span>
                <span className="text-xs text-muted-foreground">
                  {role.description}
                </span>
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

/**
 * Get human-readable label for a role
 */
export function getRoleLabel(role: CompanyMemberRole): string {
  return ROLES.find((r) => r.value === role)?.label ?? role
}

/**
 * Get role description
 */
export function getRoleDescription(role: CompanyMemberRole): string {
  return ROLES.find((r) => r.value === role)?.description ?? ''
}
