/**
 * IconSelector Component
 * Visual icon picker with search and preview
 *
 * @module admin/components/menu-builder
 * @date 2026-01-31
 */

'use client';

import React, { useState, useMemo } from 'react';
import { useTranslations } from 'next-intl';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, ChevronDown } from 'lucide-react';
import { getIconComponent, getAvailableIcons } from '@/modules/agent-dashboard/utils/menu-helpers';

// =============================================================================
// PROPS
// =============================================================================

interface IconSelectorProps {
  value: string;
  onChange: (icon: string) => void;
  disabled?: boolean;
}

// =============================================================================
// ICON CATEGORIES (for better UX)
// =============================================================================

const ICON_CATEGORIES: Record<string, string[]> = {
  'Navigation': ['LayoutDashboard', 'Home', 'ChevronDown'],
  'Documents': ['FileText', 'File', 'FileCheck', 'FileX', 'FilePlus', 'FileEdit', 'Folder', 'FolderOpen', 'ClipboardList', 'FileSearch', 'FileSpreadsheet', 'FileSignature'],
  'Status': ['Clock', 'CheckCircle', 'History', 'Calendar', 'AlertCircle', 'AlertTriangle'],
  'Finance': ['Wallet', 'CreditCard', 'Receipt', 'TrendingUp', 'BarChart3', 'Banknote', 'RefreshCw', 'Activity'],
  'Business': ['Building2', 'Car', 'Truck', 'BadgeCheck', 'Briefcase', 'Globe', 'Plane'],
  'Users': ['User', 'Users', 'UserPlus', 'UserCheck', 'UserX'],
  'Communication': ['Bell', 'Mail', 'Phone', 'MessageSquare'],
  'Settings': ['Settings', 'Shield', 'ShieldAlert', 'LogOut'],
  'Other': ['HelpCircle', 'Info', 'List'],
};

// =============================================================================
// COMPONENT
// =============================================================================

export function IconSelector({ value, onChange, disabled = false }: IconSelectorProps) {
  const t = useTranslations('admin.menuConfig.iconSelector');
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');

  // Get all available icons
  const allIcons = useMemo(() => getAvailableIcons(), []);

  // Filter icons by search
  const filteredIcons = useMemo(() => {
    if (!search) return allIcons;
    const searchLower = search.toLowerCase();
    return allIcons.filter((icon) => icon.toLowerCase().includes(searchLower));
  }, [allIcons, search]);

  // Group filtered icons by category
  const groupedIcons = useMemo(() => {
    const result: Record<string, string[]> = {};

    for (const [category, icons] of Object.entries(ICON_CATEGORIES)) {
      const filtered = icons.filter((icon) => filteredIcons.includes(icon));
      if (filtered.length > 0) {
        result[category] = filtered;
      }
    }

    // Add uncategorized icons
    const categorizedIcons = new Set(Object.values(ICON_CATEGORIES).flat());
    const uncategorized = filteredIcons.filter((icon) => !categorizedIcons.has(icon));
    if (uncategorized.length > 0) {
      result['Other'] = [...(result['Other'] || []), ...uncategorized];
    }

    return result;
  }, [filteredIcons]);

  // Get current icon component
  const CurrentIcon = getIconComponent(value);

  const handleSelect = (icon: string) => {
    onChange(icon);
    setIsOpen(false);
    setSearch('');
  };

  // Map category names to translation keys
  const getCategoryLabel = (category: string): string => {
    const categoryMap: Record<string, string> = {
      'Navigation': t('categories.navigation'),
      'Documents': t('categories.documents'),
      'Status': t('categories.status'),
      'Finance': t('categories.finance'),
      'Business': t('categories.business'),
      'Users': t('categories.users'),
      'Communication': t('categories.communication'),
      'Settings': t('categories.settings'),
      'Other': t('categories.other'),
    };
    return categoryMap[category] || category;
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={isOpen}
          disabled={disabled}
          className="w-full justify-between"
        >
          <div className="flex items-center gap-2">
            <CurrentIcon className="h-4 w-4" />
            <span className="truncate">{value || t('selectIcon')}</span>
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0" align="start">
        {/* Search */}
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('searchIcons')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9"
            />
          </div>
        </div>

        {/* Icon Grid */}
        <ScrollArea className="h-[300px]">
          <div className="p-2 space-y-4">
            {Object.entries(groupedIcons).map(([category, icons]) => (
              <div key={category}>
                <h4 className="text-xs font-medium text-muted-foreground mb-2 px-1">
                  {getCategoryLabel(category)}
                </h4>
                <div className="grid grid-cols-6 gap-1">
                  {icons.map((iconName) => {
                    const Icon = getIconComponent(iconName);
                    const isSelected = iconName === value;

                    return (
                      <button
                        key={iconName}
                        type="button"
                        onClick={() => handleSelect(iconName)}
                        className={`
                          p-2 rounded-md flex items-center justify-center
                          transition-colors hover:bg-muted
                          ${isSelected ? 'bg-primary/10 ring-1 ring-primary' : ''}
                        `}
                        title={iconName}
                      >
                        <Icon className={`h-4 w-4 ${isSelected ? 'text-primary' : ''}`} />
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}

            {filteredIcons.length === 0 && (
              <div className="text-center text-muted-foreground py-8">
                {t('noIconsFound')}
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Footer with count */}
        <div className="p-2 border-t bg-muted/30 text-xs text-muted-foreground text-center">
          {t('iconsAvailable', { count: filteredIcons.length })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
