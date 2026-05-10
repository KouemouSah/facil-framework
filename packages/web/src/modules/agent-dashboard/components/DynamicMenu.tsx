/**
 * DynamicMenu Component
 *
 * Renders dynamic menu items from backend API response.
 * Supports both single items and collapsible menu groups.
 *
 * @module agent-dashboard/components
 * @date 2026-01-19
 */

'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { cn } from '@/core/utils';
import { ChevronDown } from 'lucide-react';
import type { DynamicMenuItem, SubMenuItem } from '../types/menu-config';
import { isDynamicMenuGroup, isDynamicMenuLink } from '../types/menu-config';
import { getIconComponent } from '../utils/menu-helpers';

// =============================================================================
// PROPS INTERFACE
// =============================================================================

interface DynamicMenuProps {
  /** Menu items from API response */
  items: DynamicMenuItem[];
  /** Whether sidebar is collapsed */
  collapsed?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Called when a menu item is clicked */
  onItemClick?: (itemId: string) => void;
}

interface DynamicMenuItemProps {
  item: DynamicMenuItem;
  collapsed: boolean;
  pathname: string | null;
  expandedGroups: Set<string>;
  onToggleGroup: (id: string) => void;
  onItemClick?: (itemId: string) => void;
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function DynamicMenu({
  items,
  collapsed = false,
  className,
  onItemClick,
}: DynamicMenuProps) {
  const pathname = usePathname();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  // Auto-expand group containing active route
  useEffect(() => {
    if (!items.length) return;

    for (const item of items) {
      if (isDynamicMenuGroup(item)) {
        const hasActiveChild = item.items.some(
          (sub) =>
            pathname === sub.href || pathname?.startsWith(sub.href + '/')
        );
        if (hasActiveChild) {
          setExpandedGroups((prev) => new Set(prev).add(item.id));
          break;
        }
      }
    }
  }, [pathname, items]);

  const toggleGroup = (id: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!items.length) {
    return null;
  }

  return (
    <nav className={cn('space-y-1', className)}>
      {items.map((item) => (
        <DynamicMenuItemComponent
          key={item.id}
          item={item}
          collapsed={collapsed}
          pathname={pathname}
          expandedGroups={expandedGroups}
          onToggleGroup={toggleGroup}
          onItemClick={onItemClick}
        />
      ))}
    </nav>
  );
}

// =============================================================================
// MENU ITEM COMPONENT (single item or group)
// =============================================================================

function DynamicMenuItemComponent({
  item,
  collapsed,
  pathname,
  expandedGroups,
  onToggleGroup,
  onItemClick,
}: DynamicMenuItemProps) {
  const t = useTranslations();

  // Get translation for title key
  const getTitle = (titleKey: string): string => {
    try {
      return t(titleKey);
    } catch {
      // Fallback: extract last part of key
      const parts = titleKey.split('.');
      return parts[parts.length - 1];
    }
  };

  if (isDynamicMenuGroup(item)) {
    return (
      <MenuGroup
        group={item}
        collapsed={collapsed}
        pathname={pathname}
        isExpanded={expandedGroups.has(item.id)}
        onToggle={() => onToggleGroup(item.id)}
        getTitle={getTitle}
        onItemClick={onItemClick}
      />
    );
  }

  if (isDynamicMenuLink(item)) {
    return (
      <MenuSingleItem
        item={item}
        collapsed={collapsed}
        pathname={pathname}
        getTitle={getTitle}
        onItemClick={onItemClick}
      />
    );
  }

  return null;
}

// =============================================================================
// MENU GROUP (collapsible with sub-items)
// =============================================================================

interface MenuGroupProps {
  group: DynamicMenuItem & { items: SubMenuItem[] };
  collapsed: boolean;
  pathname: string | null;
  isExpanded: boolean;
  onToggle: () => void;
  getTitle: (key: string) => string;
  onItemClick?: (itemId: string) => void;
}

function MenuGroup({
  group,
  collapsed,
  pathname,
  isExpanded,
  onToggle,
  getTitle,
  onItemClick,
}: MenuGroupProps) {
  const Icon = getIconComponent(group.icon);
  const hasActiveChild = group.items.some(
    (sub) => pathname === sub.href || pathname?.startsWith(sub.href + '/')
  );

  return (
    <div className="pt-2">
      {/* Group header */}
      <button
        onClick={onToggle}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm w-full transition-all hover:bg-accent',
          hasActiveChild
            ? 'text-primary font-medium'
            : 'text-muted-foreground hover:text-foreground'
        )}
        title={collapsed ? getTitle(group.titleKey) : undefined}
      >
        <Icon className="h-5 w-5 flex-shrink-0" />
        {!collapsed && (
          <>
            <span className="flex-1 text-left truncate">
              {getTitle(group.titleKey)}
            </span>
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform duration-200',
                isExpanded ? 'rotate-180' : ''
              )}
            />
          </>
        )}
      </button>

      {/* Collapsible sub-items */}
      <div
        className={cn(
          'overflow-hidden transition-all duration-200 ease-in-out',
          isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
        )}
      >
        <div className={cn('space-y-1 mt-1', !collapsed && 'ml-4')}>
          {group.items.map((subItem) => (
            <MenuSubItem
              key={subItem.id}
              item={subItem}
              collapsed={collapsed}
              pathname={pathname}
              getTitle={getTitle}
              onItemClick={onItemClick}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// MENU SINGLE ITEM (no children)
// =============================================================================

interface MenuSingleItemProps {
  item: DynamicMenuItem & { href: string };
  collapsed: boolean;
  pathname: string | null;
  getTitle: (key: string) => string;
  onItemClick?: (itemId: string) => void;
}

function MenuSingleItem({
  item,
  collapsed,
  pathname,
  getTitle,
  onItemClick,
}: MenuSingleItemProps) {
  const Icon = getIconComponent(item.icon);
  const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');

  const handleClick = () => {
    onItemClick?.(item.id);
  };

  return (
    <Link
      href={item.href}
      onClick={handleClick}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all hover:bg-accent',
        isActive
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:text-foreground'
      )}
      title={collapsed ? getTitle(item.titleKey) : undefined}
    >
      <Icon className="h-5 w-5 flex-shrink-0" />
      {!collapsed && (
        <span className="truncate">{getTitle(item.titleKey)}</span>
      )}
    </Link>
  );
}

// =============================================================================
// MENU SUB-ITEM
// =============================================================================

interface MenuSubItemProps {
  item: SubMenuItem;
  collapsed: boolean;
  pathname: string | null;
  getTitle: (key: string) => string;
  onItemClick?: (itemId: string) => void;
}

function MenuSubItem({
  item,
  collapsed,
  pathname,
  getTitle,
  onItemClick,
}: MenuSubItemProps) {
  const Icon = getIconComponent(item.icon);
  const isActive = pathname === item.href || pathname?.startsWith(item.href + '/');

  const handleClick = () => {
    onItemClick?.(item.id);
  };

  return (
    <Link
      href={item.href}
      onClick={handleClick}
      className={cn(
        'flex items-center gap-3 rounded-lg px-3 py-1.5 text-sm transition-all hover:bg-accent',
        isActive
          ? 'bg-primary/10 text-primary font-medium'
          : 'text-muted-foreground hover:text-foreground'
      )}
      title={collapsed ? getTitle(item.titleKey) : undefined}
    >
      <Icon className="h-4 w-4 flex-shrink-0" />
      {!collapsed && (
        <span className="truncate">{getTitle(item.titleKey)}</span>
      )}
    </Link>
  );
}

export default DynamicMenu;
