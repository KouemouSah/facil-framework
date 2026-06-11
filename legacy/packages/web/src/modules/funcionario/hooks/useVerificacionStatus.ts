/**
 * Hook for fetching and managing verification status
 */

import { useState, useEffect, useCallback } from 'react'
import { verificacionApi } from '../services/verificacionApi'
import type { MyVerificationStatus } from '../types'

interface UseVerificacionStatusReturn {
  status: MyVerificationStatus | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useVerificacionStatus(): UseVerificacionStatusReturn {
  const [status, setStatus] = useState<MyVerificationStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await verificacionApi.getMyStatus()
      setStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al obtener el estado de verificacion')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  return {
    status,
    isLoading,
    error,
    refetch: fetchStatus,
  }
}
