/**
 * Cross-tab authentication synchronization via BroadcastChannel.
 *
 * Ensures logout/login/token-refresh propagate across all open tabs.
 * Falls back gracefully in environments where BroadcastChannel is unavailable (SSR, old browsers).
 */

type AuthEventType = 'login' | 'logout' | 'token-refresh';

interface AuthBroadcastMessage {
  type: AuthEventType;
  timestamp: number;
}

const CHANNEL_NAME = 'taxasge-auth';

let channel: BroadcastChannel | null = null;
let listeners: Array<(msg: AuthBroadcastMessage) => void> = [];

function getChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') return null;
  if (!channel) {
    try {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = (event: MessageEvent<AuthBroadcastMessage>) => {
        listeners.forEach((fn) => fn(event.data));
      };
    } catch {
      return null;
    }
  }
  return channel;
}

/**
 * Broadcast an auth event to all other tabs.
 */
export function broadcastAuthEvent(type: AuthEventType): void {
  const ch = getChannel();
  if (!ch) return;
  try {
    ch.postMessage({ type, timestamp: Date.now() } satisfies AuthBroadcastMessage);
  } catch {
    // Silently fail — non-critical
  }
}

/**
 * Listen for auth events from other tabs.
 * Returns an unsubscribe function.
 */
export function onAuthBroadcast(callback: (msg: AuthBroadcastMessage) => void): () => void {
  getChannel(); // ensure channel is initialized
  listeners.push(callback);
  return () => {
    listeners = listeners.filter((fn) => fn !== callback);
  };
}
