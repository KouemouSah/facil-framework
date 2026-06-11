/**
 * usePushTemplates Hook
 * React hook for managing push notification templates
 */

import { useState, useCallback } from 'react'
import { pushTemplatesApi } from '../services/api'
import type {
  PushTemplateCreate,
  PushTemplateUpdate,
  PushTemplateResponse,
  PushTemplateListParams,
  PushTemplateStats,
  PushNotificationPreview,
} from '../types'

interface UsePushTemplatesReturn {
  templates: PushTemplateResponse[]
  total: number
  isLoading: boolean
  error: string | null
  stats: PushTemplateStats | null
  fetchTemplates: (params?: PushTemplateListParams) => Promise<void>
  fetchStats: () => Promise<void>
  getTemplate: (id: number) => Promise<PushTemplateResponse | null>
  createTemplate: (data: PushTemplateCreate) => Promise<PushTemplateResponse | null>
  updateTemplate: (id: number, data: PushTemplateUpdate) => Promise<PushTemplateResponse | null>
  deleteTemplate: (id: number) => Promise<boolean>
  previewTemplate: (id: number, language?: string, variables?: Record<string, string>) => Promise<PushNotificationPreview | null>
}

export function usePushTemplates(): UsePushTemplatesReturn {
  const [templates, setTemplates] = useState<PushTemplateResponse[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState<PushTemplateStats | null>(null)

  const fetchTemplates = useCallback(async (params?: PushTemplateListParams) => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await pushTemplatesApi.list(params)
      setTemplates(response.templates)
      setTotal(response.total)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch push templates'
      setError(errorMessage)
      console.error('Error fetching push templates:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const statsData = await pushTemplatesApi.stats()
      setStats(statsData)
    } catch (err) {
      console.error('Error fetching push template stats:', err)
    }
  }, [])

  const getTemplate = useCallback(async (id: number): Promise<PushTemplateResponse | null> => {
    setError(null)

    try {
      const template = await pushTemplatesApi.get(id)
      return template
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch push template'
      setError(errorMessage)
      console.error('Error fetching push template:', err)
      return null
    }
  }, [])

  const createTemplate = useCallback(async (data: PushTemplateCreate): Promise<PushTemplateResponse | null> => {
    setError(null)

    try {
      const template = await pushTemplatesApi.create(data)
      // Refresh list
      await fetchTemplates()
      return template
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create push template'
      setError(errorMessage)
      console.error('Error creating push template:', err)
      return null
    }
  }, [fetchTemplates])

  const updateTemplate = useCallback(async (
    id: number,
    data: PushTemplateUpdate
  ): Promise<PushTemplateResponse | null> => {
    setError(null)

    try {
      const template = await pushTemplatesApi.update(id, data)
      // Refresh list
      await fetchTemplates()
      return template
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update push template'
      setError(errorMessage)
      console.error('Error updating push template:', err)
      return null
    }
  }, [fetchTemplates])

  const deleteTemplate = useCallback(async (id: number): Promise<boolean> => {
    setError(null)

    try {
      await pushTemplatesApi.delete(id)
      // Refresh list
      await fetchTemplates()
      return true
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete push template'
      setError(errorMessage)
      console.error('Error deleting push template:', err)
      return false
    }
  }, [fetchTemplates])

  const previewTemplate = useCallback(async (
    id: number,
    language: string = 'es',
    variables?: Record<string, string>
  ): Promise<PushNotificationPreview | null> => {
    setError(null)

    try {
      const preview = await pushTemplatesApi.preview(id, language, variables)
      return preview
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to preview push template'
      setError(errorMessage)
      console.error('Error previewing push template:', err)
      return null
    }
  }, [])

  return {
    templates,
    total,
    isLoading,
    error,
    stats,
    fetchTemplates,
    fetchStats,
    getTemplate,
    createTemplate,
    updateTemplate,
    deleteTemplate,
    previewTemplate,
  }
}
