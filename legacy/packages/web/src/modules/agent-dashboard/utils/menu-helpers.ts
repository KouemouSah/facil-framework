/**
 * Menu Helper Utilities
 *
 * Utilities for dynamic menu configuration.
 *
 * @module agent-dashboard/utils
 * @date 2026-01-19
 */

import {
  LayoutDashboard,
  FileText,
  Clock,
  CheckCircle,
  History,
  Calendar,
  Wallet,
  CreditCard,
  Receipt,
  TrendingUp,
  BarChart3,
  FileSearch,
  ClipboardList,
  Building2,
  Car,
  BadgeCheck,
  Briefcase,
  Globe,
  User,
  Settings,
  Shield,
  LogOut,
  ChevronDown,
  AlertCircle,
  Bell,
  Mail,
  Phone,
  MessageSquare,
  HelpCircle,
  Info,
  Folder,
  FolderOpen,
  File,
  FileCheck,
  FileX,
  FilePlus,
  FileEdit,
  Users,
  UserPlus,
  UserCheck,
  UserX,
  Home,
  // Treasury icons
  RefreshCw,
  Activity,
  ShieldAlert,
  FileSpreadsheet,
  Banknote,
  // Escalation icons
  AlertTriangle,
  List,
  // Workflow icons
  Plane,
  Truck,
  FileSignature,
  type LucideIcon,
} from 'lucide-react';

// =============================================================================
// ICON MAPPING
// =============================================================================

/**
 * Map icon string names to Lucide components.
 * Used for dynamic menus where icons come from backend as strings.
 */
const ICON_MAP: Record<string, LucideIcon> = {
  // Layout & Navigation
  LayoutDashboard,
  Home,
  Dashboard: LayoutDashboard,
  ChevronDown,

  // Documents & Files
  FileText,
  File,
  FileCheck,
  FileX,
  FilePlus,
  FileEdit,
  Folder,
  FolderOpen,
  ClipboardList,
  FileSearch,
  FileSpreadsheet,
  FileSignature,

  // Time & Status
  Clock,
  CheckCircle,
  History,
  Calendar,
  AlertCircle,

  // Finance & Payment
  Wallet,
  CreditCard,
  Receipt,
  TrendingUp,
  BarChart3,
  Banknote,
  RefreshCw,
  Activity,

  // Entities & Business
  Building2,
  Car,
  Truck,
  BadgeCheck,
  IdCard: BadgeCheck, // Alias
  Briefcase,
  Globe,
  Plane,

  // Users
  User,
  Users,
  UserPlus,
  UserCheck,
  UserX,

  // Communication
  Bell,
  Mail,
  Phone,
  MessageSquare,

  // Settings & Security
  Settings,
  Shield,
  ShieldAlert,
  LogOut,

  // Alerts & Lists
  AlertTriangle,
  List,

  // UI Elements
  HelpCircle,
  Info,
};

/**
 * Get Lucide icon component from string name.
 *
 * @param iconName - Icon name (e.g., 'LayoutDashboard', 'FileText')
 * @returns Lucide icon component, defaults to FileText if not found
 */
export function getIconComponent(iconName: string): LucideIcon {
  return ICON_MAP[iconName] || FileText;
}

/**
 * Check if an icon name is valid (exists in the map).
 *
 * @param iconName - Icon name to check
 * @returns true if icon exists
 */
export function isValidIcon(iconName: string): boolean {
  return iconName in ICON_MAP;
}

/**
 * Get list of all available icon names.
 *
 * @returns Array of icon names
 */
export function getAvailableIcons(): string[] {
  return Object.keys(ICON_MAP);
}

// =============================================================================
// MENU UTILITIES
// =============================================================================

/**
 * Filter menu items by user permissions.
 *
 * @param items - Array of menu items
 * @param userPermissions - Set of user's permissions
 * @param isSupervisor - Whether user is a supervisor (bypasses permissions)
 * @returns Filtered menu items
 */
export function filterMenuByPermissions<T extends { permission?: string }>(
  items: T[],
  userPermissions: Set<string>,
  isSupervisor: boolean = false
): T[] {
  if (isSupervisor) {
    return items; // Supervisors see all menus
  }

  return items.filter((item) => {
    if (!item.permission) {
      return true; // No permission required
    }
    return userPermissions.has(item.permission);
  });
}

/**
 * Find menu item by ID (recursive search).
 *
 * @param items - Array of menu items
 * @param id - Item ID to find
 * @returns Found item or undefined
 */
export function findMenuItemById<T extends { id: string; items?: T[] }>(
  items: T[],
  id: string
): T | undefined {
  for (const item of items) {
    if (item.id === id) {
      return item;
    }
    if (item.items) {
      const found = findMenuItemById(item.items, id);
      if (found) {
        return found;
      }
    }
  }
  return undefined;
}

/**
 * Get all menu item IDs (flattened).
 *
 * @param items - Array of menu items
 * @returns Array of all item IDs
 */
export function getAllMenuIds<T extends { id: string; items?: T[] }>(
  items: T[]
): string[] {
  const ids: string[] = [];

  for (const item of items) {
    ids.push(item.id);
    if (item.items) {
      ids.push(...getAllMenuIds(item.items));
    }
  }

  return ids;
}

/**
 * Prefix all hrefs with locale.
 *
 * @param items - Array of menu items
 * @param locale - Locale string (e.g., 'es', 'fr', 'en')
 * @returns Menu items with prefixed hrefs
 */
export function prefixMenuHrefs<
  T extends { href?: string; items?: Array<{ href: string }> }
>(items: T[], locale: string): T[] {
  return items.map((item) => ({
    ...item,
    href: item.href
      ? item.href.startsWith('/')
        ? `/${locale}${item.href}`
        : item.href
      : undefined,
    items: item.items?.map((sub) => ({
      ...sub,
      href: sub.href.startsWith('/') ? `/${locale}${sub.href}` : sub.href,
    })),
  }));
}
