/**
 * ChatSettingsPanel Component
 * Settings panel for chat widget with language, theme, and notification preferences
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Language selector (ES/FR/EN)
 * - Theme toggle (light/dark)
 * - Notification preferences
 * - Sound toggle
 * - Persistence to localStorage
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Globe,
  Moon,
  Sun,
  Bell,
  BellOff,
  Volume2,
  VolumeX,
  Sparkles,
  FileText,
  X,
} from 'lucide-react'
import type { ChatSettings, SupportedLanguage } from '../types'

// =============================================================================
// TYPES
// =============================================================================

export interface ChatSettingsPanelProps {
  settings: ChatSettings
  onSettingsChange: (settings: Partial<ChatSettings>) => void
  onClose?: () => void
  className?: string
}

// =============================================================================
// COMPONENT
// =============================================================================

export const ChatSettingsPanel: React.FC<ChatSettingsPanelProps> = ({
  settings,
  onSettingsChange,
  onClose,
  className = '',
}) => {
  const t = useTranslations('chatbot')

  // =============================================================================
  // HANDLERS
  // =============================================================================

  const handleLanguageChange = (language: string) => {
    onSettingsChange({ language: language as SupportedLanguage })
  }

  const handleThemeChange = (isDark: boolean) => {
    onSettingsChange({ theme: isDark ? 'dark' : 'light' })
  }

  const handleNotificationsChange = (enabled: boolean) => {
    onSettingsChange({ enableNotifications: enabled })
  }

  const handleSoundChange = (enabled: boolean) => {
    onSettingsChange({ enableSound: enabled })
  }

  const handleSuggestionsChange = (enabled: boolean) => {
    onSettingsChange({ enableSuggestions: enabled })
  }

  const handleRelatedServicesChange = (enabled: boolean) => {
    onSettingsChange({ enableRelatedServices: enabled })
  }

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className={`p-4 border-b bg-muted/50 space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-sm">{t('settings')}</h3>
        {onClose && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-6 w-6"
            aria-label={t('closeChat')}
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Language Selector */}
      <div className="space-y-2">
        <Label
          htmlFor="language-select"
          className="text-xs font-medium flex items-center gap-2"
        >
          <Globe className="h-4 w-4" />
          Language
        </Label>
        <Select
          value={settings.language}
          onValueChange={handleLanguageChange}
        >
          <SelectTrigger id="language-select" className="h-8 text-xs">
            <SelectValue placeholder="Select language" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="es">
              <span className="flex items-center gap-2">
                <span>🇪🇸</span> Español
              </span>
            </SelectItem>
            <SelectItem value="fr">
              <span className="flex items-center gap-2">
                <span>🇫🇷</span> Français
              </span>
            </SelectItem>
            <SelectItem value="en">
              <span className="flex items-center gap-2">
                <span>🇬🇧</span> English
              </span>
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Theme Toggle */}
      <div className="flex items-center justify-between">
        <Label
          htmlFor="theme-toggle"
          className="text-xs font-medium flex items-center gap-2 cursor-pointer"
        >
          {settings.theme === 'dark' ? (
            <Moon className="h-4 w-4" />
          ) : (
            <Sun className="h-4 w-4" />
          )}
          Dark Mode
        </Label>
        <Switch
          id="theme-toggle"
          checked={settings.theme === 'dark'}
          onCheckedChange={handleThemeChange}
          aria-label="Toggle dark mode"
        />
      </div>

      {/* Notifications Toggle */}
      <div className="flex items-center justify-between">
        <Label
          htmlFor="notifications-toggle"
          className="text-xs font-medium flex items-center gap-2 cursor-pointer"
        >
          {settings.enableNotifications ? (
            <Bell className="h-4 w-4" />
          ) : (
            <BellOff className="h-4 w-4" />
          )}
          {settings.enableNotifications
            ? t('notificationsEnabled')
            : t('notificationsDisabled')}
        </Label>
        <Switch
          id="notifications-toggle"
          checked={settings.enableNotifications}
          onCheckedChange={handleNotificationsChange}
          aria-label="Toggle notifications"
        />
      </div>

      {/* Sound Toggle */}
      <div className="flex items-center justify-between">
        <Label
          htmlFor="sound-toggle"
          className="text-xs font-medium flex items-center gap-2 cursor-pointer"
        >
          {settings.enableSound ? (
            <Volume2 className="h-4 w-4" />
          ) : (
            <VolumeX className="h-4 w-4" />
          )}
          {settings.enableSound ? t('soundOn') : t('soundOff')}
        </Label>
        <Switch
          id="sound-toggle"
          checked={settings.enableSound}
          onCheckedChange={handleSoundChange}
          aria-label="Toggle sound"
        />
      </div>

      {/* Suggestions Toggle */}
      <div className="flex items-center justify-between">
        <Label
          htmlFor="suggestions-toggle"
          className="text-xs font-medium flex items-center gap-2 cursor-pointer"
        >
          <Sparkles className="h-4 w-4" />
          {t('suggestions')}
        </Label>
        <Switch
          id="suggestions-toggle"
          checked={settings.enableSuggestions}
          onCheckedChange={handleSuggestionsChange}
          aria-label="Toggle suggestions"
        />
      </div>

      {/* Related Services Toggle */}
      <div className="flex items-center justify-between">
        <Label
          htmlFor="related-services-toggle"
          className="text-xs font-medium flex items-center gap-2 cursor-pointer"
        >
          <FileText className="h-4 w-4" />
          {t('relatedServices')}
        </Label>
        <Switch
          id="related-services-toggle"
          checked={settings.enableRelatedServices}
          onCheckedChange={handleRelatedServicesChange}
          aria-label="Toggle related services"
        />
      </div>
    </div>
  )
}

export default ChatSettingsPanel
