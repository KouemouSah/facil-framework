/**
 * MenuPreview Component
 * Live preview of how the sidebar will look
 *
 * @module admin/components/menu-builder
 * @date 2026-01-31
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { ChevronDown, Eye, Monitor, Smartphone } from 'lucide-react';
import { getIconComponent } from '@/modules/agent-dashboard/utils/menu-helpers';
import type { MenuItem } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface MenuPreviewProps {
  menus: MenuItem[];
  roleCode?: string;
  entityCode?: string;
}

// =============================================================================
// PREVIEW MENU ITEM
// =============================================================================

interface PreviewMenuItemProps {
  item: MenuItem;
  isActive?: boolean;
}

function PreviewMenuItem({ item, isActive }: PreviewMenuItemProps) {
  const [isOpen, setIsOpen] = useState(true);
  const Icon = getIconComponent(item.icon);
  const isGroup = Array.isArray(item.items) && item.items.length > 0;

  if (isGroup) {
    return (
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted/50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Icon className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">
                {item.titleKey.split('.').pop() || item.id}
              </span>
            </div>
            <ChevronDown
              className={`h-4 w-4 text-muted-foreground transition-transform ${
                isOpen ? 'rotate-180' : ''
              }`}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="ml-4 pl-3 border-l border-muted space-y-1 mt-1">
            {item.items!.map((subItem) => {
              const SubIcon = getIconComponent(subItem.icon);
              return (
                <button
                  key={subItem.id}
                  type="button"
                  className="w-full flex items-center gap-3 px-3 py-1.5 rounded-md hover:bg-muted/50 text-left transition-colors"
                >
                  <SubIcon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    {subItem.titleKey.split('.').pop() || subItem.id}
                  </span>
                </button>
              );
            })}
          </div>
        </CollapsibleContent>
      </Collapsible>
    );
  }

  return (
    <button
      type="button"
      className={`w-full flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${
        isActive
          ? 'bg-primary/10 text-primary'
          : 'hover:bg-muted/50 text-foreground'
      }`}
    >
      <Icon className={`h-4 w-4 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
      <span className="text-sm font-medium">
        {item.titleKey.split('.').pop() || item.id}
      </span>
    </button>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function MenuPreview({ menus, roleCode, entityCode }: MenuPreviewProps) {
  const t = useTranslations('admin.menuConfig.menuPreview');
  const [viewMode, setViewMode] = useState<'desktop' | 'mobile'>('desktop');

  return (
    <Card className="sticky top-4">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            <Eye className="h-4 w-4" />
            {t('preview')}
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button
              variant={viewMode === 'desktop' ? 'secondary' : 'ghost'}
              size="icon"
              className="h-7 w-7"
              onClick={() => setViewMode('desktop')}
              title={t('desktop')}
            >
              <Monitor className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={viewMode === 'mobile' ? 'secondary' : 'ghost'}
              size="icon"
              className="h-7 w-7"
              onClick={() => setViewMode('mobile')}
              title={t('mobile')}
            >
              <Smartphone className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
        {(roleCode || entityCode) && (
          <div className="flex gap-2 mt-2">
            {roleCode && (
              <Badge variant="outline" className="text-xs font-mono">
                {roleCode}
              </Badge>
            )}
            {entityCode && (
              <Badge variant="secondary" className="text-xs">
                {entityCode}
              </Badge>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="p-0">
        {/* Sidebar Preview */}
        <div
          className={`
            bg-card border rounded-lg mx-4 mb-4 overflow-hidden
            ${viewMode === 'desktop' ? 'w-full' : 'w-[200px] mx-auto'}
          `}
        >
          {/* Sidebar Header */}
          <div className="p-3 border-b bg-muted/30">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-md bg-primary/10 flex items-center justify-center">
                <span className="text-xs font-bold text-primary">AG</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{t('agentDashboard')}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {roleCode || 'role_code'}
                </p>
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <ScrollArea className="h-[300px]">
            <div className="p-2 space-y-1">
              {menus.length > 0 ? (
                menus.map((menu, index) => (
                  <PreviewMenuItem
                    key={menu.id || index}
                    item={menu}
                    isActive={index === 0}
                  />
                ))
              ) : (
                <div className="p-4 text-center text-muted-foreground text-sm">
                  {t('noMenuItemsToPreview')}
                </div>
              )}
            </div>
          </ScrollArea>

          {/* Sidebar Footer */}
          <div className="p-3 border-t bg-muted/30">
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{t('menuItemsCount', { count: menus.length })}</span>
              <span>•</span>
              <span>
                {t('subItemsCount', { count: menus.reduce((acc, m) => acc + (m.items?.length || 0), 0) })}
              </span>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="px-4 pb-4">
          <p className="text-xs text-muted-foreground mb-2">{t('legend')}</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="flex items-center gap-1">
              <div className="h-3 w-3 rounded bg-primary/10" />
              {t('activeItem')}
            </span>
            <span className="flex items-center gap-1">
              <ChevronDown className="h-3 w-3" />
              {t('expandableGroup')}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
