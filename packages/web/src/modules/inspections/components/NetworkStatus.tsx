'use client'

import { useEffect, useState } from 'react'
import { Wifi, WifiOff } from 'lucide-react'

export function NetworkStatus() {
  const [isOnline, setIsOnline] = useState(true)
  const [pendingSync, setPendingSync] = useState(0)
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    setIsOnline(navigator.onLine)

    const handleOnline = () => {
      setIsOnline(true)
      // Show "back online" briefly
      setShowBanner(true)
      setTimeout(() => setShowBanner(false), 3000)

      // Trigger sync
      if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        navigator.serviceWorker.ready.then((reg) => {
          const syncReg = reg as unknown as { sync?: { register: (tag: string) => Promise<void> } }
          syncReg.sync?.register('sync-inspections').catch(() => {
            // Background Sync not supported
          })
        })
      }
    }

    const handleOffline = () => {
      setIsOnline(false)
      setShowBanner(true)
    }

    const handleSWMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OFFLINE_QUEUED') {
        setPendingSync((prev) => prev + 1)
      }
      if (event.data?.type === 'SYNC_COMPLETE') {
        setPendingSync(event.data.remaining || 0)
      }
      // Fix F3: Respond to SW token refresh requests for offline sync
      if (event.data?.type === 'REQUEST_AUTH_TOKEN' && event.ports?.[0]) {
        try {
          // Get fresh token from the existing auth system
          const tokenKey = 'taxasge_auth_token'
          const token = localStorage.getItem(tokenKey) ||
            sessionStorage.getItem(tokenKey) || null
          event.ports[0].postMessage({ token })
        } catch {
          event.ports[0].postMessage({ token: null })
        }
      }
    }

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    navigator.serviceWorker?.addEventListener('message', handleSWMessage)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      navigator.serviceWorker?.removeEventListener('message', handleSWMessage)
    }
  }, [])

  if (!showBanner && isOnline && pendingSync === 0) return null

  return (
    <div
      className={`fixed top-0 left-0 right-0 z-[100] px-4 py-2 text-center text-sm font-medium transition-all ${
        isOnline
          ? 'bg-green-500 text-white'
          : 'bg-red-500 text-white'
      }`}
    >
      <div className="flex items-center justify-center gap-2">
        {isOnline ? (
          <>
            <Wifi className="h-4 w-4" />
            <span>Conectado</span>
            {pendingSync > 0 && (
              <span className="bg-white/20 rounded-full px-2 py-0.5 text-xs">
                Sincronizando {pendingSync} inspección(es)...
              </span>
            )}
          </>
        ) : (
          <>
            <WifiOff className="h-4 w-4" />
            <span>Sin conexión — Las inspecciones se guardarán localmente</span>
            {pendingSync > 0 && (
              <span className="bg-white/20 rounded-full px-2 py-0.5 text-xs">
                {pendingSync} en espera
              </span>
            )}
          </>
        )}
      </div>
    </div>
  )
}
