'use client'

/**
 * UserSelector Component
 * Searchable dropdown for selecting a user
 *
 * @module user-permissions-admin/components
 * @author Claude Code
 * @date 2025-12-04
 */

import { useState, useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { Check, ChevronsUpDown, Loader2, User } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useSearchUsers } from '../hooks/useUserPermissions'
import type { SimpleUser } from '../types'

interface UserSelectorProps {
  value: string | null
  onValueChange: (userId: string | null, user: SimpleUser | null) => void
  placeholder?: string
  disabled?: boolean
  /** Filter by role (e.g., 'agent') */
  roleFilter?: string
  /** Label for the search input */
  searchPlaceholder?: string
  /** Label for empty state */
  emptyLabel?: string
}

export function UserSelector({
  value,
  onValueChange,
  placeholder,
  disabled = false,
  roleFilter,
  searchPlaceholder,
  emptyLabel,
}: UserSelectorProps) {
  const t = useTranslations('admin.userPermissions')

  const [open, setOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedUser, setSelectedUser] = useState<SimpleUser | null>(null)

  const { data: users = [], isLoading } = useSearchUsers(searchQuery, roleFilter)

  // Update selected user display when value changes externally
  useEffect(() => {
    if (!value) {
      setSelectedUser(null)
    }
  }, [value])

  const handleSelect = (user: SimpleUser) => {
    setSelectedUser(user)
    onValueChange(user.id, user)
    setOpen(false)
    setSearchQuery('')
  }

  const handleClear = () => {
    setSelectedUser(null)
    onValueChange(null, null)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          {selectedUser ? (
            <div className="flex items-center gap-2 truncate">
              <User className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="truncate">
                {selectedUser.first_name} {selectedUser.last_name}
              </span>
              <span className="text-muted-foreground text-sm truncate">
                ({selectedUser.email})
              </span>
            </div>
          ) : (
            <span className="text-muted-foreground">
              {placeholder || t('selectUser') || 'Select a user...'}
            </span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="p-2">
          <Input
            placeholder={searchPlaceholder || t('searchUsers') || 'Search users...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-9"
          />
        </div>
        <ScrollArea className="max-h-[300px]">
          {isLoading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : searchQuery.length < 2 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              {t('typeToSearch') || 'Type at least 2 characters to search...'}
            </div>
          ) : users.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              {emptyLabel || t('noUsersFound') || 'No users found.'}
            </div>
          ) : (
            <div className="p-1">
              {users.map((user) => (
                <div
                  key={user.id}
                  onClick={() => handleSelect(user)}
                  className={cn(
                    'flex items-center gap-2 p-2 rounded-md cursor-pointer hover:bg-muted',
                    value === user.id && 'bg-muted'
                  )}
                >
                  <Check
                    className={cn(
                      'h-4 w-4 flex-shrink-0',
                      value === user.id ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  <div className="flex flex-col flex-1 min-w-0">
                    <span className="font-medium truncate">
                      {user.first_name} {user.last_name}
                    </span>
                    <span className="text-sm text-muted-foreground truncate">
                      {user.email}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded flex-shrink-0">
                    {user.role}
                  </span>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
        {selectedUser && (
          <div className="border-t p-2">
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={handleClear}
            >
              {t('clearSelection') || 'Clear selection'}
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}

export default UserSelector
