'use client'

/**
 * Mounts LogRocket exactly once per browser tab. No visual output — renders children.
 *
 * Mount HIGH in the App Router tree (inside <Providers>). Mounting it lower
 * means routes outside the subtree will not be captured.
 */

import { useEffect } from 'react'

import { initLogRocket } from '@/core/observability/logrocket'

interface LogRocketProviderProps {
  children: React.ReactNode
}

export function LogRocketProvider({ children }: LogRocketProviderProps) {
  useEffect(() => {
    initLogRocket()
  }, [])

  return <>{children}</>
}

export default LogRocketProvider
