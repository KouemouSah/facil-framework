/**
 * USSD Menu Structure Editor Component
 * Allows creating and editing USSD menu structures with tree navigation
 */

'use client'

import { useState, useCallback } from 'react'
import { Plus, Trash2, Edit2, Save, ChevronRight, ChevronDown, Menu } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import type { MenuNode, MenuOption, MenuActionType } from '../types'

interface UssdMenuEditorProps {
  menuStructure: MenuNode[]
  onChange: (menus: MenuNode[]) => void
  readOnly?: boolean
}

const ACTION_TYPES: { value: MenuActionType; label: string }[] = [
  { value: 'balance', label: 'Check Balance' },
  { value: 'payment', label: 'Make Payment' },
  { value: 'tax_info', label: 'Tax Information' },
  { value: 'service_search', label: 'Search Services' },
  { value: 'declaration_status', label: 'Declaration Status' },
  { value: 'support', label: 'Contact Support' },
  { value: 'custom', label: 'Custom Action' },
]

// Generate a unique ID for new menus
function generateMenuId(): string {
  return `menu_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

export function UssdMenuEditor({ menuStructure, onChange, readOnly = false }: UssdMenuEditorProps) {
  const [selectedMenuId, setSelectedMenuId] = useState<string | null>(
    menuStructure.find(m => m.isRoot)?.id || menuStructure[0]?.id || null
  )
  const [editingMenu, setEditingMenu] = useState<MenuNode | null>(null)
  const [editingOption, setEditingOption] = useState<{ menuId: string; index: number; option: MenuOption } | null>(null)
  const [expandedMenus, setExpandedMenus] = useState<Set<string>>(new Set(menuStructure.map(m => m.id)))
  const [deleteMenuId, setDeleteMenuId] = useState<string | null>(null)

  const selectedMenu = menuStructure.find(m => m.id === selectedMenuId)

  const toggleExpand = (menuId: string) => {
    setExpandedMenus(prev => {
      const newSet = new Set(prev)
      if (newSet.has(menuId)) {
        newSet.delete(menuId)
      } else {
        newSet.add(menuId)
      }
      return newSet
    })
  }

  const handleAddMenu = useCallback(() => {
    const newMenu: MenuNode = {
      id: generateMenuId(),
      titleEs: 'New Menu',
      titleFr: '',
      titleEn: '',
      options: [
        {
          key: '1',
          labelEs: 'Option 1',
          labelFr: '',
          labelEn: '',
          action: 'custom',
        }
      ],
      isRoot: menuStructure.length === 0,
      parentMenu: undefined,
    }
    onChange([...menuStructure, newMenu])
    setSelectedMenuId(newMenu.id)
    setEditingMenu(newMenu)
  }, [menuStructure, onChange])

  const handleUpdateMenu = useCallback((updatedMenu: MenuNode) => {
    const newMenus = menuStructure.map(m =>
      m.id === updatedMenu.id ? updatedMenu : m
    )
    onChange(newMenus)
    setEditingMenu(null)
  }, [menuStructure, onChange])

  const handleDeleteMenu = useCallback((menuId: string) => {
    const menu = menuStructure.find(m => m.id === menuId)
    if (!menu) return

    // Don't allow deleting the root menu if it's the only one
    if (menu.isRoot && menuStructure.length === 1) {
      return
    }

    // Remove the menu and update references
    const newMenus = menuStructure
      .filter(m => m.id !== menuId)
      .map(m => ({
        ...m,
        // If this was the root menu, make another one root
        isRoot: menu.isRoot && m.id === menuStructure.find(mm => mm.id !== menuId)?.id ? true : m.isRoot,
        // Remove navigation references to the deleted menu
        options: m.options.map(opt => ({
          ...opt,
          nextMenu: opt.nextMenu === menuId ? undefined : opt.nextMenu,
          action: opt.nextMenu === menuId ? 'custom' as MenuActionType : opt.action,
        }))
      }))

    onChange(newMenus)
    setDeleteMenuId(null)
    if (selectedMenuId === menuId) {
      setSelectedMenuId(newMenus[0]?.id || null)
    }
  }, [menuStructure, onChange, selectedMenuId])

  const handleAddOption = useCallback((menuId: string) => {
    const menu = menuStructure.find(m => m.id === menuId)
    if (!menu) return

    const existingKeys = menu.options.map(o => o.key)
    let newKey = '1'
    for (let i = 1; i <= 9; i++) {
      if (!existingKeys.includes(String(i))) {
        newKey = String(i)
        break
      }
    }

    const newOption: MenuOption = {
      key: newKey,
      labelEs: `Option ${newKey}`,
      labelFr: '',
      labelEn: '',
      action: 'custom',
    }

    const newMenus = menuStructure.map(m =>
      m.id === menuId
        ? { ...m, options: [...m.options, newOption] }
        : m
    )
    onChange(newMenus)
  }, [menuStructure, onChange])

  const handleUpdateOption = useCallback((menuId: string, optionIndex: number, updatedOption: MenuOption) => {
    const newMenus = menuStructure.map(m => {
      if (m.id === menuId) {
        const newOptions = [...m.options]
        newOptions[optionIndex] = updatedOption
        return { ...m, options: newOptions }
      }
      return m
    })
    onChange(newMenus)
    setEditingOption(null)
  }, [menuStructure, onChange])

  const handleDeleteOption = useCallback((menuId: string, optionIndex: number) => {
    const menu = menuStructure.find(m => m.id === menuId)
    if (!menu || menu.options.length <= 1) return // Keep at least one option

    const newMenus = menuStructure.map(m => {
      if (m.id === menuId) {
        return {
          ...m,
          options: m.options.filter((_, i) => i !== optionIndex)
        }
      }
      return m
    })
    onChange(newMenus)
  }, [menuStructure, onChange])

  const handleSetRoot = useCallback((menuId: string) => {
    const newMenus = menuStructure.map(m => ({
      ...m,
      isRoot: m.id === menuId,
    }))
    onChange(newMenus)
  }, [menuStructure, onChange])

  const renderMenuTree = () => {
    const rootMenus = menuStructure.filter(m => m.isRoot)
    const childMenus = menuStructure.filter(m => !m.isRoot)

    return (
      <div className="space-y-1">
        {rootMenus.map(menu => (
          <div key={menu.id}>
            <div
              className={`flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-muted ${
                selectedMenuId === menu.id ? 'bg-muted' : ''
              }`}
              onClick={() => setSelectedMenuId(menu.id)}
            >
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={(e) => { e.stopPropagation(); toggleExpand(menu.id) }}
              >
                {expandedMenus.has(menu.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </Button>
              <Menu className="h-4 w-4 text-muted-foreground" />
              <span className="flex-1 truncate text-sm">{menu.titleEs}</span>
              <Badge variant="secondary" className="text-xs">Root</Badge>
            </div>
            {expandedMenus.has(menu.id) && (
              <div className="ml-8 space-y-1">
                {menu.options
                  .filter(opt => opt.nextMenu)
                  .map(opt => {
                    const childMenu = menuStructure.find(m => m.id === opt.nextMenu)
                    if (!childMenu) return null
                    return (
                      <div
                        key={childMenu.id}
                        className={`flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-muted ${
                          selectedMenuId === childMenu.id ? 'bg-muted' : ''
                        }`}
                        onClick={() => setSelectedMenuId(childMenu.id)}
                      >
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        <span className="flex-1 truncate text-sm">{childMenu.titleEs}</span>
                      </div>
                    )
                  })}
              </div>
            )}
          </div>
        ))}
        {childMenus.filter(m => !menuStructure.some(pm => pm.options.some(o => o.nextMenu === m.id))).map(menu => (
          <div
            key={menu.id}
            className={`flex items-center gap-2 p-2 rounded cursor-pointer hover:bg-muted ${
              selectedMenuId === menu.id ? 'bg-muted' : ''
            }`}
            onClick={() => setSelectedMenuId(menu.id)}
          >
            <div className="w-6" />
            <Menu className="h-4 w-4 text-muted-foreground" />
            <span className="flex-1 truncate text-sm">{menu.titleEs}</span>
            <Badge variant="outline" className="text-xs">Orphan</Badge>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Menu Tree */}
      <Card className="md:col-span-1">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center justify-between">
            Menu Tree
            {!readOnly && (
              <Button size="sm" variant="outline" onClick={handleAddMenu}>
                <Plus className="h-4 w-4 mr-1" />
                Add
              </Button>
            )}
          </CardTitle>
          <CardDescription className="text-xs">
            {menuStructure.length} menu(s)
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          {menuStructure.length === 0 ? (
            <div className="text-center py-4 text-muted-foreground text-sm">
              No menus yet. Click &quot;Add&quot; to create one.
            </div>
          ) : (
            renderMenuTree()
          )}
        </CardContent>
      </Card>

      {/* Menu Editor */}
      <Card className="md:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center justify-between">
            {selectedMenu ? (
              <>
                <span className="truncate">{selectedMenu.titleEs}</span>
                {!readOnly && (
                  <div className="flex gap-1">
                    {!selectedMenu.isRoot && (
                      <Button size="sm" variant="outline" onClick={() => handleSetRoot(selectedMenu.id)}>
                        Set as Root
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => setEditingMenu(selectedMenu)}>
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setDeleteMenuId(selectedMenu.id)}
                      disabled={selectedMenu.isRoot && menuStructure.length === 1}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                )}
              </>
            ) : (
              'Select a menu'
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {selectedMenu ? (
            <div className="space-y-4">
              {/* Menu Info */}
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div>
                  <Label className="text-xs text-muted-foreground">Spanish</Label>
                  <p className="truncate">{selectedMenu.titleEs}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">French</Label>
                  <p className="truncate">{selectedMenu.titleFr || '-'}</p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">English</Label>
                  <p className="truncate">{selectedMenu.titleEn || '-'}</p>
                </div>
              </div>

              <Separator />

              {/* Options */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label className="text-sm font-medium">Menu Options</Label>
                  {!readOnly && (
                    <Button size="sm" variant="outline" onClick={() => handleAddOption(selectedMenu.id)}>
                      <Plus className="h-4 w-4 mr-1" />
                      Add Option
                    </Button>
                  )}
                </div>
                <div className="space-y-2">
                  {selectedMenu.options.map((option, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 p-2 border rounded-md bg-background"
                    >
                      <Badge variant="outline" className="font-mono">{option.key}</Badge>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm truncate">{option.labelEs}</p>
                        <p className="text-xs text-muted-foreground">
                          {option.nextMenu
                            ? `Go to: ${menuStructure.find(m => m.id === option.nextMenu)?.titleEs || option.nextMenu}`
                            : `Action: ${ACTION_TYPES.find(a => a.value === option.action)?.label || option.action}`
                          }
                        </p>
                      </div>
                      {!readOnly && (
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => setEditingOption({ menuId: selectedMenu.id, index, option })}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDeleteOption(selectedMenu.id, index)}
                            disabled={selectedMenu.options.length <= 1}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Select a menu from the tree to view and edit it.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Menu Dialog */}
      {editingMenu && (
        <EditMenuDialog
          menu={editingMenu}
          onSave={handleUpdateMenu}
          onCancel={() => setEditingMenu(null)}
        />
      )}

      {/* Edit Option Dialog */}
      {editingOption && (
        <EditOptionDialog
          option={editingOption.option}
          menus={menuStructure}
          currentMenuId={editingOption.menuId}
          onSave={(opt) => handleUpdateOption(editingOption.menuId, editingOption.index, opt)}
          onCancel={() => setEditingOption(null)}
        />
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={deleteMenuId !== null} onOpenChange={() => setDeleteMenuId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Menu</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this menu? Any options that navigate to this menu will be updated.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMenuId && handleDeleteMenu(deleteMenuId)}
              className="bg-destructive text-destructive-foreground"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

// Edit Menu Dialog Component
function EditMenuDialog({
  menu,
  onSave,
  onCancel
}: {
  menu: MenuNode
  onSave: (menu: MenuNode) => void
  onCancel: () => void
}) {
  const [titleEs, setTitleEs] = useState(menu.titleEs)
  const [titleFr, setTitleFr] = useState(menu.titleFr || '')
  const [titleEn, setTitleEn] = useState(menu.titleEn || '')
  const [menuId, setMenuId] = useState(menu.id)

  const handleSave = () => {
    onSave({
      ...menu,
      id: menuId,
      titleEs,
      titleFr: titleFr || undefined,
      titleEn: titleEn || undefined,
    })
  }

  return (
    <AlertDialog open onOpenChange={onCancel}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Edit Menu</AlertDialogTitle>
        </AlertDialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="menuId">Menu ID</Label>
            <Input
              id="menuId"
              value={menuId}
              onChange={(e) => setMenuId(e.target.value)}
              placeholder="unique_menu_id"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="titleEs">Title (Spanish) *</Label>
            <Input
              id="titleEs"
              value={titleEs}
              onChange={(e) => setTitleEs(e.target.value)}
              placeholder="Menu title in Spanish"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="titleFr">Title (French)</Label>
            <Input
              id="titleFr"
              value={titleFr}
              onChange={(e) => setTitleFr(e.target.value)}
              placeholder="Menu title in French"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="titleEn">Title (English)</Label>
            <Input
              id="titleEn"
              value={titleEn}
              onChange={(e) => setTitleEn(e.target.value)}
              placeholder="Menu title in English"
            />
          </div>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleSave} disabled={!titleEs.trim() || !menuId.trim()}>
            <Save className="h-4 w-4 mr-2" />
            Save
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// Edit Option Dialog Component
function EditOptionDialog({
  option,
  menus,
  currentMenuId,
  onSave,
  onCancel,
}: {
  option: MenuOption
  menus: MenuNode[]
  currentMenuId: string
  onSave: (option: MenuOption) => void
  onCancel: () => void
}) {
  const [key, setKey] = useState(option.key)
  const [labelEs, setLabelEs] = useState(option.labelEs)
  const [labelFr, setLabelFr] = useState(option.labelFr || '')
  const [labelEn, setLabelEn] = useState(option.labelEn || '')
  const [navigationType, setNavigationType] = useState<'action' | 'menu'>(option.nextMenu ? 'menu' : 'action')
  const [nextMenu, setNextMenu] = useState(option.nextMenu || '')
  const [action, setAction] = useState<MenuActionType>(option.action || 'custom')

  const handleSave = () => {
    onSave({
      key,
      labelEs,
      labelFr: labelFr || undefined,
      labelEn: labelEn || undefined,
      nextMenu: navigationType === 'menu' ? nextMenu : undefined,
      action: navigationType === 'action' ? action : undefined,
    })
  }

  const availableMenus = menus.filter(m => m.id !== currentMenuId)

  return (
    <AlertDialog open onOpenChange={onCancel}>
      <AlertDialogContent className="max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>Edit Option</AlertDialogTitle>
        </AlertDialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="key">Key *</Label>
            <Input
              id="key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="1, 2, *, #"
              maxLength={5}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="labelEs">Label (Spanish) *</Label>
            <Input
              id="labelEs"
              value={labelEs}
              onChange={(e) => setLabelEs(e.target.value)}
              placeholder="Option label"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="labelFr">Label (French)</Label>
            <Input
              id="labelFr"
              value={labelFr}
              onChange={(e) => setLabelFr(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="labelEn">Label (English)</Label>
            <Input
              id="labelEn"
              value={labelEn}
              onChange={(e) => setLabelEn(e.target.value)}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label>When selected</Label>
            <Select value={navigationType} onValueChange={(v) => setNavigationType(v as 'action' | 'menu')}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="action">Execute Action</SelectItem>
                <SelectItem value="menu">Navigate to Menu</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {navigationType === 'action' ? (
            <div className="space-y-2">
              <Label>Action Type</Label>
              <Select value={action} onValueChange={(v) => setAction(v as MenuActionType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACTION_TYPES.map(a => (
                    <SelectItem key={a.value} value={a.value}>{a.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="space-y-2">
              <Label>Target Menu</Label>
              <Select value={nextMenu} onValueChange={setNextMenu}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a menu" />
                </SelectTrigger>
                <SelectContent>
                  {availableMenus.map(m => (
                    <SelectItem key={m.id} value={m.id}>{m.titleEs}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {availableMenus.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Create more menus to enable navigation.
                </p>
              )}
            </div>
          )}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={handleSave}
            disabled={!key.trim() || !labelEs.trim() || (navigationType === 'menu' && !nextMenu)}
          >
            <Save className="h-4 w-4 mr-2" />
            Save
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
