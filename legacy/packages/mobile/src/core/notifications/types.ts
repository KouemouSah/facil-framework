/**
 * Notification types — shared across the notifications feature.
 *
 * The mobile app receives push notifications from FCM (Android) and APNs (iOS),
 * sent by the backend `PushSendingService`. The backend payload mirrors
 * `firebase_admin.messaging.Message`:
 *   - `notification` (title/body) for visible push
 *   - `data` (string→string map) for routing / state updates
 *
 * The data payload conventions used by the backend are documented in
 * `app/modules/communications/services/push_sending_service.py`.
 */

/** Android notification channel identifiers. */
export type NotificationChannelId =
  | 'default'
  | 'payment'
  | 'agent_decision'
  | 'appointment'
  | 'support'
  | 'documents';

/** Type discriminator carried by `data.type` from the backend. */
export type NotificationType =
  | 'payment_completed'
  | 'payment_rejected'
  | 'payment_receipt_ready'
  | 'agent_decision'
  | 'agent_documents_requested'
  | 'appointment_reminder'
  | 'appointment_rescheduled'
  | 'support_ticket_replied'
  | 'document_expiring'
  | 'license_issued'
  | 'request_submitted'
  | 'company_invitation'
  | 'generic';

/** Raw push payload `data` map (all values are strings — FCM/APNs constraint). */
export interface NotificationDataPayload {
  type?: NotificationType | string;
  /** Pre-built deep link (e.g. `facil://payments/abc/result`). Takes priority if set. */
  deep_link?: string;
  /** Entity id (request id, payment id, ticket number…). */
  entity_id?: string;
  /** Notification id from `notification_log` (for read tracking). */
  notif_id?: string;
  /** Optional: comma-separated React Query keys to invalidate on receipt. */
  invalidate_keys?: string;
  /** Channel hint from backend (overrides default routing). */
  channel?: NotificationChannelId;
  [key: string]: string | undefined;
}

/** A notification persisted to MMKV after being received. */
export interface StoredNotification {
  id: string;
  channelId: NotificationChannelId;
  title: string;
  body: string;
  data: NotificationDataPayload;
  receivedAt: number;
  readAt: number | null;
  deepLink: string | null;
}

/** Permission request outcome. */
export type NotificationPermissionStatus =
  | 'granted'
  | 'denied'
  | 'undetermined';

/** Native device token from the OS push provider. */
export interface NativeDeviceToken {
  token: string;
  platform: 'android' | 'ios';
}

/** Lifecycle status of `useDeviceTokenRegistration`. */
export type DeviceTokenRegistrationStatus =
  | 'idle'
  | 'requesting_permission'
  | 'permission_denied'
  | 'fetching_token'
  | 'registering'
  | 'registered'
  | 'error';
