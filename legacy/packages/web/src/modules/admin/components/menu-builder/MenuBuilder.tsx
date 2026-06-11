/**
 * MenuBuilder Component
 * Visual menu configuration builder with drag-and-drop and preview
 *
 * @module admin/components/menu-builder
 * @date 2026-01-31
 */

'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Menu,
  Plus,
  GripVertical,
  ChevronUp,
  ChevronDown,
  Code,
  AlertCircle,
  FolderPlus,
  LinkIcon,
  Loader2,
  Wand2,
} from 'lucide-react';
import { getIconComponent } from '@/modules/agent-dashboard/utils/menu-helpers';
import { MenuItemEditor } from './MenuItemEditor';
import { MenuPreview } from './MenuPreview';
import type { MenuItem, ValidationError } from './types';
import {
  createEmptyMenuItem,
  validateMenuConfig,
  menuConfigToJson,
  parseMenuConfig,
} from './types';

// =============================================================================
// PROPS
// =============================================================================

interface MenuBuilderProps {
  /** Initial menu configuration (from roles.menu_config) */
  initialConfig: Record<string, unknown> | null;
  /** Callback when menu changes */
  onChange: (menus: MenuItem[], isAutoMode: boolean) => void;
  /** Whether changes are being saved */
  isSaving?: boolean;
  /** Role code for context */
  roleCode?: string;
  /** Entity code for context */
  entityCode?: string;
  /** Whether editing is disabled */
  disabled?: boolean;
}

// =============================================================================
// MENU LIST ITEM
// =============================================================================

interface MenuListItemProps {
  item: MenuItem;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
}

function MenuListItem({
  item,
  index,
  isSelected,
  onSelect,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
}: MenuListItemProps) {
  const Icon = getIconComponent(item.icon);
  const isGroup = Array.isArray(item.items) && item.items.length > 0;

  return (
    <div
      className={`
        flex items-center gap-2 p-2 rounded-md border cursor-pointer transition-colors
        ${isSelected ? 'bg-primary/5 border-primary' : 'hover:bg-muted/50 border-transparent'}
      `}
      onClick={onSelect}
    >
      <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
      <Icon className="h-4 w-4 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {item.titleKey.split('.').pop() || item.id || `Item ${index + 1}`}
          </span>
          {isGroup && (
            <Badge variant="secondary" className="text-[10px] h-4">
              {item.items!.length} items
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground font-mono truncate">
          {item.id}
        </p>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={(e) => {
            e.stopPropagation();
            onMoveUp();
          }}
          disabled={!canMoveUp}
          aria-label={`Move ${item.titleKey || item.id} up`}
        >
          <ChevronUp className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={(e) => {
            e.stopPropagation();
            onMoveDown();
          }}
          disabled={!canMoveDown}
          aria-label={`Move ${item.titleKey || item.id} down`}
        >
          <ChevronDown className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function MenuBuilder({
  initialConfig,
  onChange,
  isSaving = false,
  roleCode,
  entityCode,
  disabled = false,
}: MenuBuilderProps) {
  const t = useTranslations('admin.menuConfig.menuBuilder');

  // State
  const [menus, setMenus] = useState<MenuItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isAutoMode, setIsAutoMode] = useState(initialConfig === null);
  const [showJsonSheet, setShowJsonSheet] = useState(false);
  const [showSwitchDialog, setShowSwitchDialog] = useState(false);
  const [pendingSwitchMode, setPendingSwitchMode] = useState<boolean | null>(null);
  const [errors, setErrors] = useState<ValidationError[]>([]);

  // Initialize from config
  useEffect(() => {
    if (initialConfig) {
      const parsedMenus = parseMenuConfig(initialConfig);
      setMenus(parsedMenus);
      setIsAutoMode(false);
    } else {
      setMenus([]);
      setIsAutoMode(true);
    }
  }, [initialConfig]);

  // Notify parent of changes
  useEffect(() => {
    onChange(menus, isAutoMode);
  }, [menus, isAutoMode, onChange]);

  // Validate on change
  useEffect(() => {
    if (!isAutoMode) {
      const validationErrors = validateMenuConfig(menus);
      setErrors(validationErrors);
    } else {
      setErrors([]);
    }
  }, [menus, isAutoMode]);

  // Handlers
  const handleAddMenu = useCallback((isGroup: boolean) => {
    const newItem = createEmptyMenuItem(isGroup);
    setMenus((prev) => [...prev, newItem]);
    setSelectedIndex(menus.length);
  }, [menus.length]);

  const handleUpdateMenu = useCallback((index: number, updatedItem: MenuItem) => {
    setMenus((prev) => {
      const newMenus = [...prev];
      newMenus[index] = updatedItem;
      return newMenus;
    });
  }, []);

  const handleDeleteMenu = useCallback((index: number) => {
    setMenus((prev) => prev.filter((_, i) => i !== index));
    setSelectedIndex(null);
  }, []);

  const handleMoveMenu = useCallback((index: number, direction: 'up' | 'down') => {
    setMenus((prev) => {
      const newMenus = [...prev];
      const targetIndex = direction === 'up' ? index - 1 : index + 1;
      if (targetIndex < 0 || targetIndex >= newMenus.length) return prev;
      [newMenus[index], newMenus[targetIndex]] = [newMenus[targetIndex], newMenus[index]];
      return newMenus;
    });
    setSelectedIndex(direction === 'up' ? selectedIndex! - 1 : selectedIndex! + 1);
  }, [selectedIndex]);

  const handleModeSwitch = useCallback((newAutoMode: boolean) => {
    if (menus.length > 0 && !newAutoMode === isAutoMode) {
      setPendingSwitchMode(newAutoMode);
      setShowSwitchDialog(true);
    } else {
      setIsAutoMode(newAutoMode);
      if (newAutoMode) {
        setMenus([]);
        setSelectedIndex(null);
      }
    }
  }, [menus.length, isAutoMode]);

  const confirmModeSwitch = useCallback(() => {
    if (pendingSwitchMode !== null) {
      setIsAutoMode(pendingSwitchMode);
      if (pendingSwitchMode) {
        setMenus([]);
        setSelectedIndex(null);
      }
    }
    setShowSwitchDialog(false);
    setPendingSwitchMode(null);
  }, [pendingSwitchMode]);

  const selectedItem = selectedIndex !== null ? menus[selectedIndex] : null;

  return (
    <div className="space-y-4">
      {/* Mode Toggle */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label className="text-base font-medium">{t('modeTitle')}</Label>
              <p className="text-sm text-muted-foreground">
                {isAutoMode ? t('modeAuto') : t('modeManual')}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-sm ${isAutoMode ? 'font-medium text-primary' : 'text-muted-foreground'}`}>
                <Wand2 className="h-4 w-4 inline mr-1" />
                {t('auto')}
              </span>
              <Switch
                checked={!isAutoMode}
                onCheckedChange={(checked) => handleModeSwitch(!checked)}
                disabled={disabled || isSaving}
              />
              <span className={`text-sm ${!isAutoMode ? 'font-medium text-primary' : 'text-muted-foreground'}`}>
                <Menu className="h-4 w-4 inline mr-1" />
                {t('manual')}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Auto Mode Message */}
      {isAutoMode && (
        <Card className="border-blue-200 bg-blue-50/50">
          <CardContent className="pt-4">
            <div className="flex items-start gap-3">
              <Wand2 className="h-5 w-5 text-blue-600 mt-0.5" />
              <div>
                <p className="font-medium text-blue-900">{t('autoModeActive')}</p>
                <p className="text-sm text-blue-700 mt-1">
                  {t('autoModeDescription')}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Manual Mode Builder */}
      {!isAutoMode && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Menu List */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">{t('menuItems')}</CardTitle>
                  <Badge variant="secondary">{menus.length}</Badge>
                </div>
                <CardDescription>
                  {t('clickToEditDragToReorder')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {/* Add Buttons */}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => handleAddMenu(false)}
                    disabled={disabled || isSaving}
                  >
                    <LinkIcon className="h-4 w-4 mr-1" />
                    {t('addLink')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => handleAddMenu(true)}
                    disabled={disabled || isSaving}
                  >
                    <FolderPlus className="h-4 w-4 mr-1" />
                    {t('addGroup')}
                  </Button>
                </div>

                <Separator />

                {/* Menu List */}
                <ScrollArea className="h-[350px]">
                  {menus.length > 0 ? (
                    <div className="space-y-1 pr-2">
                      {menus.map((menu, index) => (
                        <MenuListItem
                          key={menu.id || index}
                          item={menu}
                          index={index}
                          isSelected={selectedIndex === index}
                          onSelect={() => setSelectedIndex(index)}
                          onMoveUp={() => handleMoveMenu(index, 'up')}
                          onMoveDown={() => handleMoveMenu(index, 'down')}
                          canMoveUp={index > 0}
                          canMoveDown={index < menus.length - 1}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="p-4 text-center text-muted-foreground border border-dashed rounded-md">
                      <Plus className="h-8 w-8 mx-auto mb-2 opacity-50" />
                      <p className="text-sm">{t('noMenuItems')}</p>
                      <p className="text-xs">{t('clickLinkOrGroup')}</p>
                    </div>
                  )}
                </ScrollArea>

                {/* Validation Errors */}
                {errors.length > 0 && (
                  <>
                    <Separator />
                    <div className="space-y-1">
                      <Label className="text-xs text-destructive flex items-center gap-1">
                        <AlertCircle className="h-3 w-3" />
                        {t('validationErrors')} ({errors.length})
                      </Label>
                      <div className="text-xs text-destructive space-y-0.5 max-h-[80px] overflow-auto">
                        {errors.slice(0, 5).map((err, i) => (
                          <p key={i}>{t(err.message, err.params)}</p>
                        ))}
                        {errors.length > 5 && (
                          <p className="text-muted-foreground">
                            {t('andMore', { count: errors.length - 5 })}
                          </p>
                        )}
                      </div>
                    </div>
                  </>
                )}

                {/* Actions */}
                <Separator />
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={() => setShowJsonSheet(true)}
                >
                  <Code className="h-4 w-4 mr-2" />
                  {t('viewJson')}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Center: Editor */}
          <div className="lg:col-span-1">
            {selectedItem ? (
              <MenuItemEditor
                item={selectedItem}
                onChange={(updated) => handleUpdateMenu(selectedIndex!, updated)}
                onDelete={() => handleDeleteMenu(selectedIndex!)}
                disabled={disabled || isSaving}
              />
            ) : (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center text-muted-foreground py-12">
                    <Menu className="h-12 w-12 mx-auto mb-4 opacity-30" />
                    <p className="font-medium">{t('menuItems')}</p>
                    <p className="text-sm mt-1">
                      {t('clickToEditDragToReorder')}
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Preview */}
          <div className="lg:col-span-1">
            <MenuPreview
              menus={menus}
              roleCode={roleCode}
              entityCode={entityCode}
            />
          </div>
        </div>
      )}

      {/* JSON Sheet */}
      <Sheet open={showJsonSheet} onOpenChange={setShowJsonSheet}>
        <SheetContent className="sm:max-w-[600px]">
          <SheetHeader>
            <SheetTitle>{t('menuConfigJson')}</SheetTitle>
            <SheetDescription>
              {t('jsonDescription')}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4">
            <pre className="p-4 bg-muted rounded-md overflow-auto max-h-[70vh] text-xs font-mono">
              {menuConfigToJson(menus)}
            </pre>
          </div>
        </SheetContent>
      </Sheet>

      {/* Mode Switch Confirmation Dialog */}
      <AlertDialog open={showSwitchDialog} onOpenChange={setShowSwitchDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingSwitchMode ? t('switchToAutoMode') : t('switchToManualMode')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingSwitchMode ? t('switchToAutoDescription') : t('switchToManualDescription')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setPendingSwitchMode(null)}>
              {t('cancel')}
            </AlertDialogCancel>
            <AlertDialogAction onClick={confirmModeSwitch}>
              {pendingSwitchMode ? t('switchToAuto') : t('switchToManual')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Saving Indicator */}
      {isSaving && (
        <div className="fixed bottom-4 right-4 flex items-center gap-2 bg-background border rounded-md px-4 py-2 shadow-lg">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">{t('saving')}</span>
        </div>
      )}
    </div>
  );
}
