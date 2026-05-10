"use client"

import * as React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/core/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export interface SafeSelectItem {
  value: string
  label: string
  description?: string
}

export interface SafeSelectProps {
  /** Current selected value */
  value: string
  /** Callback when value changes */
  onValueChange: (value: string) => void
  /** Placeholder text when no value selected */
  placeholder?: string
  /** Show loading state (disables select, no dropdown) */
  isLoading?: boolean
  /** Loading state message */
  loadingMessage?: string
  /** Show empty state (disables select, no dropdown) */
  isEmpty?: boolean
  /** Empty state message */
  emptyMessage?: string
  /** Disable the select */
  disabled?: boolean
  /** Items to display in dropdown */
  items: SafeSelectItem[]
  /** Optional "all" option prepended to items (e.g., "All sites") */
  allOption?: { value: string; label: string }
  /** Additional className for the trigger */
  className?: string
  /** Name attribute for form integration */
  name?: string
}

/**
 * SafeSelect — wrapper around shadcn Select that prevents crashes from empty-value SelectItems.
 *
 * Handles loading/empty states OUTSIDE the SelectContent (no disabled SelectItems with value="").
 * Guarantees every SelectItem has a non-empty string value.
 */
export function SafeSelect({
  value,
  onValueChange,
  placeholder = "Sélectionner...",
  isLoading = false,
  loadingMessage = "Chargement...",
  isEmpty,
  emptyMessage = "Aucune option disponible",
  disabled = false,
  items,
  allOption,
  className,
  name,
}: SafeSelectProps) {
  const effectiveIsEmpty = isEmpty ?? (items.length === 0 && !isLoading)

  // Loading state: show disabled trigger with spinner
  if (isLoading) {
    return (
      <Select disabled>
        <SelectTrigger className={cn("text-muted-foreground", className)}>
          <span className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {loadingMessage}
          </span>
        </SelectTrigger>
      </Select>
    )
  }

  // Empty state: show disabled trigger with message
  if (effectiveIsEmpty && !allOption) {
    return (
      <Select disabled>
        <SelectTrigger className={cn("text-muted-foreground", className)}>
          <span>{emptyMessage}</span>
        </SelectTrigger>
      </Select>
    )
  }

  return (
    <Select
      value={value}
      onValueChange={onValueChange}
      disabled={disabled}
      name={name}
    >
      <SelectTrigger className={className}>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allOption && (
          <SelectItem value={allOption.value}>
            {allOption.label}
          </SelectItem>
        )}
        {items.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.description ? (
              <span className="flex flex-col">
                <span>{item.label}</span>
                <span className="text-xs text-muted-foreground">
                  {item.description}
                </span>
              </span>
            ) : (
              item.label
            )}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
