/**
 * useChatSettings Hook
 * Persistent settings management for chatbot
 *
 * @module chatbot/hooks
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Language preference
 * - Theme (light/dark)
 * - Display settings (suggestions, sources, etc.)
 * - Sound preferences
 * - localStorage persistence
 * - Type-safe settings
 */

'use client'

import { useState, useEffect, useCallback } from 'react'
import type { ChatSettings, SupportedLanguage } from '../types'

// =============================================================================
// TYPES
// =============================================================================

export interface UseChatSettingsOptions {
  persistToStorage?: boolean
  onSettingsChange?: (settings: ChatSettings) => void
}

export interface UseChatSettingsReturn {
  // State
  settings: ChatSettings

  // Actions
  updateSettings: (updates: Partial<ChatSettings>) => void
  setLanguage: (language: SupportedLanguage) => void
  setTheme: (theme: 'light' | 'dark') => void
  toggleSuggestions: () => void
  toggleRelatedServices: () => void
  toggleSources: () => void
  toggleSound: () => void
  resetSettings: () => void
}

// =============================================================================
// DEFAULT SETTINGS
// =============================================================================

const DEFAULT_SETTINGS: ChatSettings = {
  language: 'es',
  enableSuggestions: true,
  enableRelatedServices: true,
  enableSources: true,
  theme: 'light',
  enableSound: false,
  enableNotifications: false,
}

// =============================================================================
// STORAGE KEY
// =============================================================================

const STORAGE_KEY = 'chatbot_settings'

// =============================================================================
// HOOK
// =============================================================================

export function useChatSettings(
  options: UseChatSettingsOptions = {}
): UseChatSettingsReturn {
  const {
    persistToStorage = true,
    onSettingsChange,
  } = options

  // State
  const [settings, setSettings] = useState<ChatSettings>(DEFAULT_SETTINGS)

  // =============================================================================
  // STORAGE HELPERS
  // =============================================================================

  const saveToStorage = useCallback(
    (newSettings: ChatSettings) => {
      if (!persistToStorage || typeof window === 'undefined') return

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings))
      } catch (err) {
        console.error('Failed to save settings to storage:', err)
      }
    },
    [persistToStorage]
  )

  const loadFromStorage = useCallback((): ChatSettings | null => {
    if (!persistToStorage || typeof window === 'undefined') return null

    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Merge with defaults to ensure all fields exist
        return { ...DEFAULT_SETTINGS, ...parsed }
      }
    } catch (err) {
      console.error('Failed to load settings from storage:', err)
    }

    return null
  }, [persistToStorage])

  const clearStorage = useCallback(() => {
    if (typeof window === 'undefined') return

    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (err) {
      console.error('Failed to clear settings from storage:', err)
    }
  }, [])

  // =============================================================================
  // EFFECTS
  // =============================================================================

  // Load settings on mount
  useEffect(() => {
    const loaded = loadFromStorage()
    if (loaded) {
      setSettings(loaded)
    }
  }, [loadFromStorage])

  // =============================================================================
  // ACTIONS
  // =============================================================================

  /**
   * Update multiple settings at once
   */
  const updateSettings = useCallback(
    (updates: Partial<ChatSettings>) => {
      setSettings((prev) => {
        const newSettings = { ...prev, ...updates }
        saveToStorage(newSettings)

        if (onSettingsChange) {
          onSettingsChange(newSettings)
        }

        return newSettings
      })
    },
    [saveToStorage, onSettingsChange]
  )

  /**
   * Set language
   */
  const setLanguage = useCallback(
    (language: SupportedLanguage) => {
      updateSettings({ language })
    },
    [updateSettings]
  )

  /**
   * Set theme
   */
  const setTheme = useCallback(
    (theme: 'light' | 'dark') => {
      updateSettings({ theme })
    },
    [updateSettings]
  )

  /**
   * Toggle suggestions
   */
  const toggleSuggestions = useCallback(() => {
    updateSettings({ enableSuggestions: !settings.enableSuggestions })
  }, [settings.enableSuggestions, updateSettings])

  /**
   * Toggle related services
   */
  const toggleRelatedServices = useCallback(() => {
    updateSettings({ enableRelatedServices: !settings.enableRelatedServices })
  }, [settings.enableRelatedServices, updateSettings])

  /**
   * Toggle sources
   */
  const toggleSources = useCallback(() => {
    updateSettings({ enableSources: !settings.enableSources })
  }, [settings.enableSources, updateSettings])

  /**
   * Toggle sound
   */
  const toggleSound = useCallback(() => {
    updateSettings({ enableSound: !settings.enableSound })
  }, [settings.enableSound, updateSettings])

  /**
   * Reset to default settings
   */
  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_SETTINGS)
    clearStorage()

    if (onSettingsChange) {
      onSettingsChange(DEFAULT_SETTINGS)
    }
  }, [clearStorage, onSettingsChange])

  // =============================================================================
  // RETURN
  // =============================================================================

  return {
    // State
    settings,

    // Actions
    updateSettings,
    setLanguage,
    setTheme,
    toggleSuggestions,
    toggleRelatedServices,
    toggleSources,
    toggleSound,
    resetSettings,
  }
}

export default useChatSettings
