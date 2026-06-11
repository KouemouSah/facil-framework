/**
 * Facil Control — Service Worker
 *
 * Cache strategies:
 * - Static assets (CSS, JS, images, fonts): Cache-first
 * - API filter data (zones, sectors): Stale-while-revalidate
 * - API search/inspections: Network-first (fresh data priority)
 * - Offline queue: Background Sync for POST requests
 */

const CACHE_NAME = 'facil-control-v1'
const STATIC_CACHE = 'facil-static-v1'
const API_CACHE = 'facil-api-v1'

const STATIC_ASSETS = [
  '/logo.png',
  '/logo1.png',
  '/manifest.json',
]

// API paths that benefit from caching (reference data)
const CACHE_API_PATHS = [
  '/api/v1/service-bundles/zones',
  '/api/v1/cities',
  '/api/v1/fiscal-services',
]

// API paths that should always go network-first
const NETWORK_FIRST_PATHS = [
  '/api/v1/inspections',
  '/api/v1/oms/queue',
]

// POST requests to queue when offline
const OFFLINE_QUEUE_PATHS = [
  '/api/v1/inspections/',
  '/api/v1/inspections/*/complete',
  '/api/v1/inspections/*/mise-en-demeure',
  '/api/v1/inspections/*/seal',
  '/api/v1/inspections/*/collect',
]

// ============================================================
// Install
// ============================================================
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS))
  )
  self.skipWaiting()
})

// ============================================================
// Activate — clean old caches
// ============================================================
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME && key !== STATIC_CACHE && key !== API_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  )
  self.clients.claim()
})

// ============================================================
// Fetch — strategy routing
// ============================================================
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Skip non-GET for caching (POST handled separately)
  if (event.request.method !== 'GET') {
    // Queue POST inspections when offline
    if (event.request.method === 'POST' && url.pathname.includes('/inspections')) {
      event.respondWith(networkOrQueue(event.request))
    }
    return
  }

  // Static assets: cache-first
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(event.request))
    return
  }

  // API reference data: stale-while-revalidate
  if (CACHE_API_PATHS.some((p) => url.pathname.includes(p))) {
    event.respondWith(staleWhileRevalidate(event.request))
    return
  }

  // API search/inspections: network-first
  if (NETWORK_FIRST_PATHS.some((p) => url.pathname.includes(p))) {
    event.respondWith(networkFirst(event.request))
    return
  }

  // Default: network only
  return
})

// ============================================================
// Strategies
// ============================================================

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    return new Response('Offline', { status: 503 })
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(API_CACHE)
  const cached = await cache.match(request)

  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) {
      cache.put(request, response.clone())
    }
    return response
  }).catch(() => cached)

  return cached || fetchPromise
}

async function networkFirst(request) {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(API_CACHE)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    const cached = await caches.match(request)
    if (cached) return cached
    return new Response(JSON.stringify({ error: 'offline' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

async function networkOrQueue(request) {
  try {
    return await fetch(request)
  } catch {
    // Store in IndexedDB for later sync
    const body = await request.clone().text()
    await storeOfflineRequest({
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body,
      timestamp: Date.now(),
    })

    // Notify client
    const clients = await self.clients.matchAll()
    clients.forEach((client) => {
      client.postMessage({
        type: 'OFFLINE_QUEUED',
        url: request.url,
      })
    })

    return new Response(JSON.stringify({
      queued: true,
      message: 'Inspection guardada localmente. Se sincronizará cuando haya conexión.',
    }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

// ============================================================
// IndexedDB for offline queue
// ============================================================

function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('facil-offline', 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('requests')) {
        db.createObjectStore('requests', { keyPath: 'id', autoIncrement: true })
      }
      if (!db.objectStoreNames.contains('inspections')) {
        db.createObjectStore('inspections', { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function storeOfflineRequest(data) {
  const db = await openDB()
  const tx = db.transaction('requests', 'readwrite')
  tx.objectStore('requests').add(data)
  return tx.complete
}

async function getOfflineRequests() {
  const db = await openDB()
  return new Promise((resolve) => {
    const tx = db.transaction('requests', 'readonly')
    const req = tx.objectStore('requests').getAll()
    req.onsuccess = () => resolve(req.result)
  })
}

async function clearOfflineRequest(id) {
  const db = await openDB()
  const tx = db.transaction('requests', 'readwrite')
  tx.objectStore('requests').delete(id)
}

// ============================================================
// Background Sync
// ============================================================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-inspections') {
    event.waitUntil(syncOfflineRequests())
  }
})

async function syncOfflineRequests() {
  const requests = await getOfflineRequests()
  let synced = 0

  // Fix m1: Get fresh auth token from the active client before syncing
  let freshToken = null
  try {
    const clients = await self.clients.matchAll({ type: 'window' })
    if (clients.length > 0) {
      // Request fresh token from client
      const messageChannel = new MessageChannel()
      const tokenPromise = new Promise((resolve) => {
        messageChannel.port1.onmessage = (event) => resolve(event.data?.token)
        setTimeout(() => resolve(null), 3000) // 3s timeout
      })
      clients[0].postMessage({ type: 'REQUEST_AUTH_TOKEN' }, [messageChannel.port2])
      freshToken = await tokenPromise
    }
  } catch {
    // Token refresh failed, try with stored headers
  }

  for (const req of requests) {
    try {
      const headers = { ...req.headers }
      // Fix m1: Use fresh token if available, replacing potentially expired one
      if (freshToken) {
        headers['Authorization'] = 'Bearer ' + freshToken
      }

      const response = await fetch(req.url, {
        method: req.method,
        headers,
        body: req.body,
      })

      if (response.ok) {
        await clearOfflineRequest(req.id)
        synced++
      } else if (response.status === 401) {
        // Token expired and no fresh token available — skip, retry later
        break
      }
    } catch {
      // Still offline, will retry on next sync
      break
    }
  }

  if (synced > 0) {
    const clients = await self.clients.matchAll()
    clients.forEach((client) => {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        synced,
        remaining: requests.length - synced,
      })
    })
  }
}

// ============================================================
// Helpers
// ============================================================

function isStaticAsset(url) {
  return (
    url.pathname.endsWith('.js') ||
    url.pathname.endsWith('.css') ||
    url.pathname.endsWith('.png') ||
    url.pathname.endsWith('.jpg') ||
    url.pathname.endsWith('.svg') ||
    url.pathname.endsWith('.woff2') ||
    url.pathname.endsWith('.ico')
  )
}

// ============================================================
// Push notifications (future)
// ============================================================
self.addEventListener('push', (event) => {
  if (!event.data) return

  const data = event.data.json()
  event.waitUntil(
    self.registration.showNotification(data.title || 'Facil Control', {
      body: data.body || '',
      icon: '/logo.png',
      badge: '/logo.png',
      data: data.url ? { url: data.url } : undefined,
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  if (event.notification.data?.url) {
    event.waitUntil(self.clients.openWindow(event.notification.data.url))
  }
})
