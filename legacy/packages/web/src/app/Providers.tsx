'use client'

/**
 * Global Providers
 * Wraps the application with necessary providers (React Query, etc.)
 *
 * @module app/Providers
 * @author Claude Code
 * @date 2025-12-05
 */

import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { LogRocketProvider } from '@/components/observability/LogRocketProvider'

/**
 * Create a new QueryClient with default configuration
 */
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Default stale time: 5 minutes
        staleTime: 5 * 60 * 1000,
        // Default cache time: 10 minutes
        gcTime: 10 * 60 * 1000,
        // Retry failed requests 1 time
        retry: 1,
        // Don't refetch on window focus
        refetchOnWindowFocus: false,
        // Refetch on mount if data is stale
        refetchOnMount: true,
      },
      mutations: {
        // Retry failed mutations 0 times
        retry: 0,
      },
    },
  })
}

// Browser: Create a singleton QueryClient
let browserQueryClient: QueryClient | undefined = undefined

function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always make a new query client
    return makeQueryClient()
  } else {
    // Browser: use singleton pattern to avoid creating new clients on re-renders
    if (!browserQueryClient) browserQueryClient = makeQueryClient()
    return browserQueryClient
  }
}

interface ProvidersProps {
  children: React.ReactNode
}

/**
 * Global providers wrapper for the application
 */
export function Providers({ children }: ProvidersProps) {
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      <LogRocketProvider>
        {children}
      </LogRocketProvider>
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      )}
    </QueryClientProvider>
  )
}

export default Providers
