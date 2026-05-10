/**
 * RoleSelector Component
 * Dropdown selector for choosing roles with filtering and grouping
 *
 * @module permissions-admin/components
 * @author Claude Code
 * @date 2025-11-17
 */

"use client";

import React from "react";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
  SelectSeparator,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Shield, Building2, Globe } from "lucide-react";
import type { Role } from "../types";
import { cn } from "@/core/utils";

// =============================================================================
// TYPES
// =============================================================================

interface RoleSelectorProps {
  /**
   * Available roles to select from
   */
  roles: Role[];
  /**
   * Currently selected role ID
   */
  value?: string;
  /**
   * Callback when selection changes
   */
  onValueChange?: (roleId: string) => void;
  /**
   * Placeholder text when no role selected
   */
  placeholder?: string;
  /**
   * Filter to show only system or custom roles
   */
  filterType?: "system" | "custom" | "all";
  /**
   * Group roles by entity type
   */
  groupByEntity?: boolean;
  /**
   * Show system badge for system roles
   */
  showSystemBadge?: boolean;
  /**
   * Disabled state
   */
  disabled?: boolean;
  /**
   * Additional class name
   */
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Selector for choosing a role with rich display options
 *
 * - Groups roles by entity type (DGI, Ministry, Global)
 * - Shows system/custom badges
 * - Filters by system or custom roles
 * - Displays entity type icons
 *
 * @example
 * ```tsx
 * <RoleSelector
 *   roles={roles}
 *   value={selectedRoleId}
 *   onValueChange={setSelectedRoleId}
 *   groupByEntity
 *   showSystemBadge
 * />
 * ```
 */
export function RoleSelector({
  roles,
  value,
  onValueChange,
  placeholder = "Sélectionner un rôle",
  filterType = "all",
  groupByEntity = false,
  showSystemBadge = true,
  disabled = false,
  className,
}: RoleSelectorProps) {
  // Filter roles based on filterType
  const filteredRoles = React.useMemo(() => {
    if (filterType === "all") return roles;
    if (filterType === "system") return roles.filter((r) => r.is_system);
    if (filterType === "custom") return roles.filter((r) => !r.is_system);
    return roles;
  }, [roles, filterType]);

  // Group roles by entity type if requested
  const groupedRoles = React.useMemo(() => {
    if (!groupByEntity) {
      return { all: filteredRoles };
    }

    const groups: Record<string, Role[]> = {
      global: [],
      dgi: [],
      ministry: [],
      other: [],
    };

    filteredRoles.forEach((role) => {
      if (!role.entity_type) {
        groups.global.push(role);
      } else if (role.entity_type === "DGI") {
        groups.dgi.push(role);
      } else if (role.entity_type === "Ministry") {
        groups.ministry.push(role);
      } else {
        groups.other.push(role);
      }
    });

    return groups;
  }, [filteredRoles, groupByEntity]);

  // Get entity type icon
  const getEntityIcon = (entityType: string | null) => {
    if (!entityType) return <Globe className="h-4 w-4" />;
    if (entityType === "DGI") return <Building2 className="h-4 w-4" />;
    if (entityType === "Ministry") return <Building2 className="h-4 w-4 text-blue-500" />;
    return <Shield className="h-4 w-4" />;
  };

  // Render role item
  const renderRoleItem = (role: Role) => (
    <SelectItem key={role.id} value={role.id}>
      <div className="flex items-center gap-2">
        {getEntityIcon(role.entity_type)}
        <span className="flex-1">{role.name}</span>
        {showSystemBadge && role.is_system && (
          <Badge variant="outline" className="ml-2 text-xs">
            Système
          </Badge>
        )}
      </div>
    </SelectItem>
  );

  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {groupByEntity ? (
          <>
            {groupedRoles.global.length > 0 && (
              <SelectGroup>
                <SelectLabel className="flex items-center gap-2">
                  <Globe className="h-4 w-4" />
                  Rôles Globaux
                </SelectLabel>
                {groupedRoles.global.map(renderRoleItem)}
              </SelectGroup>
            )}

            {groupedRoles.dgi.length > 0 && (
              <>
                {groupedRoles.global.length > 0 && <SelectSeparator />}
                <SelectGroup>
                  <SelectLabel className="flex items-center gap-2">
                    <Building2 className="h-4 w-4" />
                    DGI
                  </SelectLabel>
                  {groupedRoles.dgi.map(renderRoleItem)}
                </SelectGroup>
              </>
            )}

            {groupedRoles.ministry.length > 0 && (
              <>
                {(groupedRoles.global.length > 0 || groupedRoles.dgi.length > 0) && (
                  <SelectSeparator />
                )}
                <SelectGroup>
                  <SelectLabel className="flex items-center gap-2">
                    <Building2 className="h-4 w-4 text-blue-500" />
                    Ministères
                  </SelectLabel>
                  {groupedRoles.ministry.map(renderRoleItem)}
                </SelectGroup>
              </>
            )}

            {groupedRoles.other.length > 0 && (
              <>
                <SelectSeparator />
                <SelectGroup>
                  <SelectLabel>Autres</SelectLabel>
                  {groupedRoles.other.map(renderRoleItem)}
                </SelectGroup>
              </>
            )}
          </>
        ) : (
          <SelectGroup>
            {filteredRoles.map(renderRoleItem)}
          </SelectGroup>
        )}
      </SelectContent>
    </Select>
  );
}

// =============================================================================
// SIMPLE VARIANT
// =============================================================================

interface SimpleRoleSelectorProps {
  /**
   * Available roles
   */
  roles: Role[];
  /**
   * Selected role ID
   */
  value?: string;
  /**
   * Change handler
   */
  onValueChange?: (roleId: string) => void;
  /**
   * Placeholder
   */
  placeholder?: string;
  /**
   * Disabled
   */
  disabled?: boolean;
  /**
   * Class name
   */
  className?: string;
}

/**
 * Simple role selector without grouping or badges
 *
 * @example
 * ```tsx
 * <SimpleRoleSelector
 *   roles={roles}
 *   value={roleId}
 *   onValueChange={setRoleId}
 * />
 * ```
 */
export function SimpleRoleSelector({
  roles,
  value,
  onValueChange,
  placeholder = "Sélectionner un rôle",
  disabled = false,
  className,
}: SimpleRoleSelectorProps) {
  return (
    <Select value={value} onValueChange={onValueChange} disabled={disabled}>
      <SelectTrigger className={cn("w-full", className)}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {roles.map((role) => (
            <SelectItem key={role.id} value={role.id}>
              {role.name}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default RoleSelector;
