/**
 * Query Provider for Permissions Admin Module
 * Provides React Query context for the permissions-admin module
 *
 * @module permissions-admin/providers
 * @author Claude Code
 * @date 2025-11-17
 */

"use client";

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

// =============================================================================
// QUERY CLIENT CONFIGURATION
// =============================================================================

/**
 * Create a new QueryClient with default configuration for permissions admin
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
        // Don't refetch on window focus in admin panel
        refetchOnWindowFocus: false,
        // Refetch on mount if data is stale
        refetchOnMount: true,
      },
      mutations: {
        // Retry failed mutations 0 times (fail fast for admin operations)
        retry: 0,
      },
    },
  });
}

// Browser: Create a singleton QueryClient
let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (typeof window === "undefined") {
    // Server: always make a new query client
    return makeQueryClient();
  } else {
    // Browser: use singleton pattern to avoid creating new clients on re-renders
    if (!browserQueryClient) browserQueryClient = makeQueryClient();
    return browserQueryClient;
  }
}

// =============================================================================
// PROVIDER COMPONENT
// =============================================================================

interface QueryProviderProps {
  children: React.ReactNode;
  /**
   * Show React Query Devtools (default: true in development, false in production)
   */
  showDevtools?: boolean;
}

/**
 * Provides React Query context for the permissions-admin module
 *
 * Usage:
 * ```tsx
 * <QueryProvider>
 *   <PermissionsAdminPage />
 * </QueryProvider>
 * ```
 */
export function QueryProvider({ children, showDevtools }: QueryProviderProps) {
  const queryClient = getQueryClient();

  const shouldShowDevtools =
    showDevtools !== undefined
      ? showDevtools
      : process.env.NODE_ENV === "development";

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {shouldShowDevtools && (
        <ReactQueryDevtools
          initialIsOpen={false}
          buttonPosition="bottom-right"
        />
      )}
    </QueryClientProvider>
  );
}

// =============================================================================
// EXPORTS
// =============================================================================

export default QueryProvider;
