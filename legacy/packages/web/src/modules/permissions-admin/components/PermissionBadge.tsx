/**
 * PermissionBadge Component
 * Displays a permission with visual indicators for critical permissions
 *
 * @module permissions-admin/components
 * @author Claude Code
 * @date 2025-11-17
 */

"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, Shield } from "lucide-react";
import type { Permission } from "../types";
import { cn } from "@/core/utils";

// =============================================================================
// TYPES
// =============================================================================

interface PermissionBadgeProps {
  /**
   * Permission object to display
   */
  permission: Permission;
  /**
   * Display mode
   * - "full": Show full permission name (e.g., "assignment.create")
   * - "action": Show only action (e.g., "create")
   * - "resource": Show resource.action (e.g., "assignment.create")
   */
  mode?: "full" | "action" | "resource";
  /**
   * Show critical indicator icon
   */
  showCriticalIcon?: boolean;
  /**
   * Size variant
   */
  size?: "sm" | "md" | "lg";
  /**
   * Additional class name
   */
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

/**
 * Displays a permission badge with visual styling
 *
 * - Critical permissions have red border and warning icon
 * - Non-critical permissions have blue/default styling
 * - Supports different display modes and sizes
 *
 * @example
 * ```tsx
 * <PermissionBadge permission={permission} mode="full" showCriticalIcon />
 * ```
 */
export function PermissionBadge({
  permission,
  mode = "full",
  showCriticalIcon = true,
  size = "md",
  className,
}: PermissionBadgeProps) {
  // Determine display text based on mode
  const displayText = React.useMemo(() => {
    switch (mode) {
      case "action":
        return permission.action;
      case "resource":
        return `${permission.resource}.${permission.action}`;
      case "full":
      default:
        return permission.name;
    }
  }, [permission, mode]);

  // Size classes
  const sizeClasses = {
    sm: "text-xs px-2 py-0.5",
    md: "text-sm px-2.5 py-1",
    lg: "text-base px-3 py-1.5",
  };

  return (
    <Badge
      variant={permission.is_critical ? "destructive" : "secondary"}
      className={cn(
        "inline-flex items-center gap-1.5 font-mono",
        sizeClasses[size],
        permission.is_critical && "border-red-500",
        className
      )}
      title={permission.description}
    >
      {showCriticalIcon && permission.is_critical && (
        <AlertTriangle className="h-3 w-3" />
      )}
      {showCriticalIcon && !permission.is_critical && (
        <Shield className="h-3 w-3 opacity-60" />
      )}
      <span>{displayText}</span>
    </Badge>
  );
}

// =============================================================================
// COMPACT VARIANT
// =============================================================================

interface PermissionBadgeCompactProps {
  /**
   * Permission name (e.g., "assignment.create")
   */
  name: string;
  /**
   * Is critical permission
   */
  isCritical?: boolean;
  /**
   * Additional class name
   */
  className?: string;
}

/**
 * Compact version of PermissionBadge for use in lists
 *
 * @example
 * ```tsx
 * <PermissionBadgeCompact name="assignment.create" isCritical={false} />
 * ```
 */
export function PermissionBadgeCompact({
  name,
  isCritical = false,
  className,
}: PermissionBadgeCompactProps) {
  return (
    <Badge
      variant={isCritical ? "destructive" : "outline"}
      className={cn(
        "inline-flex items-center gap-1 font-mono text-xs",
        isCritical && "border-red-500",
        className
      )}
    >
      {isCritical && <AlertTriangle className="h-3 w-3" />}
      <span>{name}</span>
    </Badge>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default PermissionBadge;
