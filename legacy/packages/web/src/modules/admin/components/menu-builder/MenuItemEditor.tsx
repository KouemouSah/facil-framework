/**
 * MenuItemEditor Component
 * Editor panel for a single menu item
 *
 * @module admin/components/menu-builder
 * @date 2026-01-31
 */

'use client';

import React from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import {
  Trash2,
  Plus,
  GripVertical,
  FolderOpen,
  Link as LinkIcon,
} from 'lucide-react';
import { IconSelector } from './IconSelector';
import { PermissionSelector } from './PermissionSelector';
import type { MenuItem, MenuSubItem } from './types';
import { createEmptySubItem } from './types';

// =============================================================================
// PROPS
// =============================================================================

interface MenuItemEditorProps {
  item: MenuItem;
  onChange: (item: MenuItem) => void;
  onDelete: () => void;
  disabled?: boolean;
}

interface SubItemEditorProps {
  item: MenuSubItem;
  onChange: (item: MenuSubItem) => void;
  onDelete: () => void;
  disabled?: boolean;
}

// =============================================================================
// SUB-ITEM EDITOR
// =============================================================================

function SubItemEditor({ item, onChange, onDelete, disabled }: SubItemEditorProps) {
  const t = useTranslations('admin.menuConfig.menuItemEditor');

  return (
    <div className="flex items-start gap-2 p-3 bg-muted/30 rounded-md border">
      <GripVertical className="h-4 w-4 mt-2.5 text-muted-foreground cursor-grab" />

      <div className="flex-1 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">{t('id')}</Label>
            <Input
              value={item.id}
              onChange={(e) => onChange({ ...item, id: e.target.value })}
              placeholder={t('idPlaceholder')}
              disabled={disabled}
              className="h-8 text-sm font-mono"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">{t('titleKey')}</Label>
            <Input
              value={item.titleKey}
              onChange={(e) => onChange({ ...item, titleKey: e.target.value })}
              placeholder={t('titleKeyPlaceholder')}
              disabled={disabled}
              className="h-8 text-sm"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">{t('icon')}</Label>
            <IconSelector
              value={item.icon}
              onChange={(icon) => onChange({ ...item, icon })}
              disabled={disabled}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">{t('permission')}</Label>
            <PermissionSelector
              value={item.permission || ''}
              onChange={(permission) => onChange({ ...item, permission: permission || undefined })}
              disabled={disabled}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">{t('hrefRequired')}</Label>
          <Input
            value={item.href}
            onChange={(e) => onChange({ ...item, href: e.target.value })}
            placeholder={t('hrefPlaceholder')}
            disabled={disabled}
            className="h-8 text-sm font-mono"
          />
        </div>
      </div>

      <Button
        variant="ghost"
        size="icon"
        onClick={onDelete}
        disabled={disabled}
        className="h-8 w-8 text-muted-foreground hover:text-destructive"
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function MenuItemEditor({ item, onChange, onDelete, disabled }: MenuItemEditorProps) {
  const t = useTranslations('admin.menuConfig.menuItemEditor');
  const isGroup = Array.isArray(item.items);

  // Toggle between group and link
  const handleToggleType = (makeGroup: boolean) => {
    if (makeGroup) {
      onChange({
        ...item,
        href: undefined,
        items: item.items || [],
      });
    } else {
      onChange({
        ...item,
        href: item.href || '',
        items: undefined,
      });
    }
  };

  // Update sub-item
  const handleSubItemChange = (index: number, updatedSubItem: MenuSubItem) => {
    const newItems = [...(item.items || [])];
    newItems[index] = updatedSubItem;
    onChange({ ...item, items: newItems });
  };

  // Delete sub-item
  const handleSubItemDelete = (index: number) => {
    const newItems = (item.items || []).filter((_, i) => i !== index);
    onChange({ ...item, items: newItems });
  };

  // Add sub-item
  const handleAddSubItem = () => {
    onChange({
      ...item,
      items: [...(item.items || []), createEmptySubItem()],
    });
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            {isGroup ? (
              <>
                <FolderOpen className="h-4 w-4 text-amber-500" />
                {t('menuGroup')}
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 text-blue-500" />
                {t('menuLink')}
              </>
            )}
            {item.id && (
              <Badge variant="outline" className="font-mono text-xs">
                {item.id}
              </Badge>
            )}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            onClick={onDelete}
            disabled={disabled}
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Type Toggle */}
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label className="text-sm">{t('menuType')}</Label>
            <p className="text-xs text-muted-foreground">
              {isGroup ? t('containsSubItems') : t('directLink')}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-xs ${!isGroup ? 'font-medium' : 'text-muted-foreground'}`}>
              {t('link')}
            </span>
            <Switch
              checked={isGroup}
              onCheckedChange={handleToggleType}
              disabled={disabled}
            />
            <span className={`text-xs ${isGroup ? 'font-medium' : 'text-muted-foreground'}`}>
              {t('group')}
            </span>
          </div>
        </div>

        <Separator />

        {/* Basic Fields */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>{t('id')}</Label>
            <Input
              value={item.id}
              onChange={(e) => onChange({ ...item, id: e.target.value })}
              placeholder={t('idPlaceholder')}
              disabled={disabled}
              className="font-mono"
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t('titleKey')}</Label>
            <Input
              value={item.titleKey}
              onChange={(e) => onChange({ ...item, titleKey: e.target.value })}
              placeholder={t('titleKeyPlaceholder')}
              disabled={disabled}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <Label>{t('icon')}</Label>
            <IconSelector
              value={item.icon}
              onChange={(icon) => onChange({ ...item, icon })}
              disabled={disabled}
            />
          </div>
          <div className="space-y-1.5">
            <Label>{t('permission')}</Label>
            <PermissionSelector
              value={item.permission || ''}
              onChange={(permission) => onChange({ ...item, permission: permission || undefined })}
              disabled={disabled}
            />
          </div>
        </div>

        {/* Href (only for links) */}
        {!isGroup && (
          <div className="space-y-1.5">
            <Label>{t('href')}</Label>
            <Input
              value={item.href || ''}
              onChange={(e) => onChange({ ...item, href: e.target.value })}
              placeholder={t('hrefPlaceholder')}
              disabled={disabled}
              className="font-mono"
            />
          </div>
        )}

        {/* Sub-items (only for groups) */}
        {isGroup && (
          <>
            <Separator />
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>{t('subItems')} ({item.items?.length || 0})</Label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAddSubItem}
                  disabled={disabled}
                >
                  <Plus className="h-4 w-4 mr-1" />
                  {t('addSubItem')}
                </Button>
              </div>

              {item.items && item.items.length > 0 ? (
                <div className="space-y-2">
                  {item.items.map((subItem, index) => (
                    <SubItemEditor
                      key={subItem.id}
                      item={subItem}
                      onChange={(updated) => handleSubItemChange(index, updated)}
                      onDelete={() => handleSubItemDelete(index)}
                      disabled={disabled}
                    />
                  ))}
                </div>
              ) : (
                <div className="p-4 text-center text-muted-foreground bg-muted/30 rounded-md border border-dashed">
                  {t('noSubItems')}
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
