/**
 * PermissionSelector Component
 * Searchable permission picker with module grouping
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
import { Badge } from '@/components/ui/badge';
import { Search, ChevronDown, X, Shield, Key } from 'lucide-react';
import { usePermissions } from '@/modules/permissions-admin/hooks/usePermissions';

// =============================================================================
// PROPS
// =============================================================================

interface PermissionSelectorProps {
  value: string;
  onChange: (permission: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function PermissionSelector({
  value,
  onChange,
  disabled = false,
  placeholder,
}: PermissionSelectorProps) {
  const t = useTranslations('admin.menuConfig.permissionSelector');
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const displayPlaceholder = placeholder || t('noPermissionRequired');

  // Fetch all permissions
  const { data: permissions = [], isLoading } = usePermissions();

  // Filter and group permissions
  const groupedPermissions = useMemo(() => {
    const filtered = search
      ? permissions.filter(
          (p) =>
            p.name.toLowerCase().includes(search.toLowerCase()) ||
            p.description.toLowerCase().includes(search.toLowerCase())
        )
      : permissions;

    // Group by module_name
    const groups: Record<string, typeof permissions> = {};
    filtered.forEach((perm) => {
      const module = perm.module_name || 'other';
      if (!groups[module]) groups[module] = [];
      groups[module].push(perm);
    });

    // Sort modules alphabetically
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [permissions, search]);

  // Find selected permission for display
  const selectedPermission = useMemo(() => {
    return permissions.find((p) => p.name === value);
  }, [permissions, value]);

  const handleSelect = (permName: string) => {
    onChange(permName);
    setIsOpen(false);
    setSearch('');
  };

  const handleClear = () => {
    onChange('');
    setIsOpen(false);
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
          <div className="flex items-center gap-2 truncate">
            {value ? (
              <>
                <Key className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="truncate">{value}</span>
              </>
            ) : (
              <>
                <Shield className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-muted-foreground">{displayPlaceholder}</span>
              </>
            )}
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        {/* Search */}
        <div className="p-2 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={t('searchPermissions')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 h-9"
            />
          </div>
        </div>

        {/* Clear option */}
        {value && (
          <div className="p-2 border-b">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClear}
              className="w-full justify-start text-muted-foreground"
            >
              <X className="h-4 w-4 mr-2" />
              {t('clearPermission')}
            </Button>
          </div>
        )}

        {/* Permission List */}
        <ScrollArea className="h-[300px]">
          {isLoading ? (
            <div className="p-4 text-center text-muted-foreground">
              {t('loadingPermissions')}
            </div>
          ) : groupedPermissions.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground">
              {t('noPermissionsFound')}
            </div>
          ) : (
            <div className="p-2 space-y-3">
              {groupedPermissions.map(([module, perms]) => (
                <div key={module}>
                  <h4 className="text-xs font-medium text-muted-foreground mb-1 px-2 uppercase tracking-wider">
                    {module}
                  </h4>
                  <div className="space-y-0.5">
                    {perms.map((perm) => {
                      const isSelected = perm.name === value;

                      return (
                        <button
                          key={perm.id}
                          type="button"
                          onClick={() => handleSelect(perm.name)}
                          className={`
                            w-full px-2 py-1.5 rounded-md text-left
                            transition-colors hover:bg-muted
                            ${isSelected ? 'bg-primary/10' : ''}
                          `}
                        >
                          <div className="flex items-center justify-between">
                            <span className={`text-sm font-mono ${isSelected ? 'text-primary font-medium' : ''}`}>
                              {perm.name}
                            </span>
                            {perm.is_critical && (
                              <Badge variant="outline" className="text-[10px] h-5 text-amber-600 border-amber-300">
                                {t('critical')}
                              </Badge>
                            )}
                          </div>
                          {perm.description && (
                            <p className="text-xs text-muted-foreground truncate mt-0.5">
                              {perm.description}
                            </p>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>

        {/* Footer */}
        {selectedPermission && (
          <div className="p-2 border-t bg-muted/30">
            <div className="text-xs">
              <span className="text-muted-foreground">{t('selected')} </span>
              <span className="font-mono">{selectedPermission.name}</span>
            </div>
            {selectedPermission.description && (
              <p className="text-xs text-muted-foreground mt-1">
                {selectedPermission.description}
              </p>
            )}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
