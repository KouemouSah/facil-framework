'use client'

import { useEffect, useRef, useCallback, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getAccessToken } from '@/core/auth/storage'
import { rolesKeys } from './useRoles'

export interface RbacEvent {
  type: string
  data: Record<string, unknown>
  timestamp: string
}

/**
 * WebSocket hook for real-time RBAC change notifications.
 * Connects to ws://host/ws/admin?token=<jwt>
 * Auto-invalidates React Query caches when RBAC events are received.
 */
export function useRbacWebSocket(options?: { enabled?: boolean }) {
  const queryClient = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<RbacEvent | null>(null)
  const retriesRef = useRef(0)
  const maxRetries = 5

  const enabled = options?.enabled !== false

  const connect = useCallback(() => {
    if (!enabled) return

    // Use the same token source as fetchClient (in-memory + cookie fallback)
    let token: string | null = null
    try {
      token = getAccessToken()
    } catch {
      token = null
    }
    if (!token) return

    // Build WebSocket URL from current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    // API is proxied through Next.js rewrites or direct backend
    const apiBase = process.env.NEXT_PUBLIC_API_URL || ''
    let wsUrl: string

    if (apiBase) {
      // Direct backend URL — no token in query param (visible in logs)
      const url = new URL(apiBase)
      wsUrl = `${protocol}//${url.host}/ws/admin`
    } else {
      // Same host (proxied)
      wsUrl = `${protocol}//${window.location.host}/ws/admin`
    }

    try {
      // Pass JWT via Sec-WebSocket-Protocol header (not query param)
      // This prevents the token from appearing in server logs and browser history
      const ws = new WebSocket(wsUrl, [token])
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
        retriesRef.current = 0
        // Start ping every 30s
        pingIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 30000)
      }

      ws.onmessage = (event) => {
        if (event.data === 'pong') return

        try {
          const rbacEvent: RbacEvent = JSON.parse(event.data)
          setLastEvent(rbacEvent)

          // Auto-invalidate React Query caches based on event type
          if (rbacEvent.type.startsWith('rbac.')) {
            queryClient.invalidateQueries({ queryKey: rolesKeys.all })
            queryClient.invalidateQueries({ queryKey: ['permissions'] })
          }
        } catch {
          // Ignore non-JSON messages
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
        cleanup()
        // Auto-reconnect with exponential backoff
        if (enabled && retriesRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000)
          retriesRef.current++
          reconnectTimeoutRef.current = setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        // onclose will fire after onerror
      }
    } catch {
      // WebSocket construction failed — environment may not support it
    }
  }, [enabled, queryClient])

  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
      pingIntervalRef.current = null
    }
  }, [])

  const disconnect = useCallback(() => {
    cleanup()
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [cleanup])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { isConnected, lastEvent }
}
