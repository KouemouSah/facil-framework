/**
 * PermissionCheckbox Component
 * Checkbox for granting/revoking permissions with rich display
 *
 * @module permissions-admin/components
 */

"use client";

import React, { useState } from "react";
import { useTranslations } from "next-intl";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { AlertTriangle, Info } from "lucide-react";
import type { Permission } from "../types";
import { cn } from "@/core/utils";

// =============================================================================
// TYPES
// =============================================================================

interface PermissionCheckboxProps {
  permission: Permission;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  mode?: "compact" | "normal" | "detailed";
  confirmCritical?: boolean;
  disabled?: boolean;
  className?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function PermissionCheckbox({
  permission,
  checked,
  onCheckedChange,
  mode = "normal",
  confirmCritical = true,
  disabled = false,
  className,
}: PermissionCheckboxProps) {
  const t = useTranslations("admin.permissions");
  const [showCriticalDialog, setShowCriticalDialog] = useState(false);

  const handleCheckedChange = (newChecked: boolean) => {
    if (newChecked && permission.is_critical && confirmCritical) {
      setShowCriticalDialog(true);
      return;
    }
    onCheckedChange(newChecked);
  };

  const handleConfirmCritical = () => {
    setShowCriticalDialog(false);
    onCheckedChange(true);
  };

  const criticalDialog = (
    <AlertDialog open={showCriticalDialog} onOpenChange={setShowCriticalDialog}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            {t("criticalDialogTitle")}
          </AlertDialogTitle>
          <AlertDialogDescription className="space-y-2">
            <span className="block font-medium text-foreground">
              {permission.name}
            </span>
            <span className="block text-muted-foreground">
              {permission.description}
            </span>
            <span className="block">
              {t("criticalDialogDescription")}
            </span>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t("criticalDialogCancel")}</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirmCritical}
            className="bg-red-600 hover:bg-red-700"
          >
            {t("criticalDialogConfirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  // Compact mode: single line
  if (mode === "compact") {
    return (
      <>
        {criticalDialog}
        <div className={cn("flex items-center space-x-2", className)}>
          <Checkbox
            id={`permission-${permission.id}`}
            checked={checked}
            onCheckedChange={handleCheckedChange}
            disabled={disabled}
          />
          <Label
            htmlFor={`permission-${permission.id}`}
            className={cn(
              "flex items-center gap-2 text-sm font-medium leading-none cursor-pointer",
              disabled && "cursor-not-allowed opacity-50"
            )}
          >
            {permission.is_critical && (
              <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
            )}
            <span className="font-mono">{permission.name}</span>
          </Label>
        </div>
      </>
    );
  }

  // Normal mode: name + description
  if (mode === "normal") {
    return (
      <>
        {criticalDialog}
        <div className={cn("flex items-start space-x-3 py-2", className)}>
          <Checkbox
            id={`permission-${permission.id}`}
            checked={checked}
            onCheckedChange={handleCheckedChange}
            disabled={disabled}
            className="mt-1"
          />
          <div className="flex-1 space-y-1">
            <Label
              htmlFor={`permission-${permission.id}`}
              className={cn(
                "flex items-center gap-2 text-sm font-medium cursor-pointer",
                disabled && "cursor-not-allowed opacity-50"
              )}
            >
              {permission.is_critical && (
                <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
              )}
              <span className="font-mono">{permission.name}</span>
            </Label>
            <p className="text-sm text-muted-foreground">
              {permission.description}
            </p>
          </div>
        </div>
      </>
    );
  }

  // Detailed mode: name + description + module badge
  return (
    <>
      {criticalDialog}
      <div
        className={cn(
          "flex items-start space-x-3 rounded-lg border p-3",
          permission.is_critical && "border-red-200 bg-red-50/30",
          className
        )}
      >
        <Checkbox
          id={`permission-${permission.id}`}
          checked={checked}
          onCheckedChange={handleCheckedChange}
          disabled={disabled}
          className="mt-1"
        />
        <div className="flex-1 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <Label
              htmlFor={`permission-${permission.id}`}
              className={cn(
                "flex items-center gap-2 text-sm font-medium cursor-pointer",
                disabled && "cursor-not-allowed opacity-50"
              )}
            >
              {permission.is_critical && (
                <AlertTriangle className="h-4 w-4 text-red-500" />
              )}
              <span className="font-mono">{permission.name}</span>
            </Label>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-xs">
                {permission.module_name}
              </Badge>
              {permission.is_critical && (
                <Badge variant="destructive" className="text-xs">
                  {t("criticalBadge")}
                </Badge>
              )}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {permission.description}
          </p>
          {permission.is_critical && (
            <div className="flex items-start gap-2 text-xs text-amber-700">
              <Info className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
              <span>{t("criticalInfo")}</span>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// =============================================================================
// GROUP COMPONENT
// =============================================================================

interface PermissionCheckboxGroupProps {
  permissions: Permission[];
  selectedPermissions: Set<string>;
  onSelectionChange: (permissionId: string, checked: boolean) => void;
  mode?: "compact" | "normal" | "detailed";
  groupByResource?: boolean;
  confirmCritical?: boolean;
  disabled?: boolean;
  className?: string;
}

export function PermissionCheckboxGroup({
  permissions,
  selectedPermissions,
  onSelectionChange,
  mode = "normal",
  groupByResource = false,
  confirmCritical = true,
  disabled = false,
  className,
}: PermissionCheckboxGroupProps) {
  const groupedPermissions = React.useMemo(() => {
    if (!groupByResource) {
      return { all: permissions };
    }

    const groups: Record<string, Permission[]> = {};
    permissions.forEach((perm) => {
      if (!groups[perm.resource]) {
        groups[perm.resource] = [];
      }
      groups[perm.resource].push(perm);
    });

    return groups;
  }, [permissions, groupByResource]);

  return (
    <div className={cn("space-y-4", className)}>
      {Object.entries(groupedPermissions).map(([resource, perms]) => (
        <div key={resource} className="space-y-2">
          {groupByResource && (
            <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              {resource}
            </h4>
          )}
          <div className="space-y-2">
            {perms.map((perm) => (
              <PermissionCheckbox
                key={perm.id}
                permission={perm}
                checked={selectedPermissions.has(perm.id)}
                onCheckedChange={(checked) => onSelectionChange(perm.id, checked)}
                mode={mode}
                confirmCritical={confirmCritical}
                disabled={disabled}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default PermissionCheckbox;
