/**
 * Notifications storage — persist received push notifications locally.
 *
 * The backend exposes `notification_log` only to admins today, so V1 keeps a
 * client-side ring buffer in MMKV. The backend can optionally reconcile via
 * `data.notif_id` (from `notification_log.id`) when a future endpoint is added.
 *
 * Storage shape: a single MMKV string key holding a JSON array of
 * `StoredNotification`, oldest-last (push to head). Capped at MAX_ITEMS.
 */

import { MMKV } from 'react-native-mmkv';
import { Platform } from 'react-native';

import type { StoredNotification } from './types';

const MAX_ITEMS = 100;
const STORAGE_KEY = 'inbox';

const inbox = new MMKV({
  id: 'facil-notifications',
  ...(Platform.OS !== 'web' ? { encryptionKey: 'facil-notif-key' } : {}),
});

function readAll(): StoredNotification[] {
  const raw = inbox.getString(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as StoredNotification[]) : [];
  } catch {
    inbox.delete(STORAGE_KEY);
    return [];
  }
}

function writeAll(items: StoredNotification[]): void {
  inbox.set(STORAGE_KEY, JSON.stringify(items));
}

/** Insert a new notification at the head. Caps at MAX_ITEMS. */
export function addNotification(notif: StoredNotification): void {
  const items = readAll();
  // Avoid duplicates if backend pushes the same notif_id twice.
  const filtered = notif.id ? items.filter((n) => n.id !== notif.id) : items;
  filtered.unshift(notif);
  if (filtered.length > MAX_ITEMS) filtered.length = MAX_ITEMS;
  writeAll(filtered);
}

export function getNotifications(): StoredNotification[] {
  return readAll();
}

export function getUnreadCount(): number {
  return readAll().filter((n) => n.readAt === null).length;
}

export function markAsRead(id: string): void {
  const items = readAll();
  const updated = items.map((n) =>
    n.id === id && n.readAt === null ? { ...n, readAt: Date.now() } : n,
  );
  writeAll(updated);
}

export function markAllAsRead(): void {
  const now = Date.now();
  const items = readAll();
  const updated = items.map((n) => (n.readAt === null ? { ...n, readAt: now } : n));
  writeAll(updated);
}

export function deleteNotification(id: string): void {
  const items = readAll();
  writeAll(items.filter((n) => n.id !== id));
}

export function clearAll(): void {
  inbox.delete(STORAGE_KEY);
}
