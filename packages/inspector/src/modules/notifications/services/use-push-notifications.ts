/**
 * usePushNotifications Hook
 *
 * Registers for push on mount (when authenticated).
 * Handles notification taps with deep linking via Expo Router.
 */

import { useEffect, useRef, useCallback } from 'react';
import {
  addNotificationReceivedListener,
  addNotificationResponseReceivedListener,
  type Notification,
} from 'expo-notifications';
import type { EventSubscription } from 'expo-modules-core';
import { router } from 'expo-router';

import { useAuth } from '@core/hooks/use-auth';
import {
  registerForPushNotifications,
  sendPushTokenToBackend,
  parseNotificationDeepLink,
} from './push-service';

export function usePushNotifications() {
  const { isAuthenticated } = useAuth();
  const notificationListener = useRef<EventSubscription | null>(null);
  const responseListener = useRef<EventSubscription | null>(null);
  const tokenRegistered = useRef(false);

  // Handle notification tap → deep link
  const handleNotificationResponse = useCallback(
    (response: { notification: Notification }) => {
      const data = response.notification.request.content.data as Record<string, unknown>;
      const deepLink = parseNotificationDeepLink(data);
      if (deepLink) {
        setTimeout(() => {
          router.push(deepLink as never);
        }, 300);
      }
    },
    [],
  );

  useEffect(() => {
    if (!isAuthenticated) return;

    // Register push token once per session
    if (!tokenRegistered.current) {
      tokenRegistered.current = true;
      registerForPushNotifications().then((token) => {
        if (token) {
          sendPushTokenToBackend(token);
        }
      });
    }

    // Foreground notification listener (shows alert via handler in push-service.ts)
    notificationListener.current = addNotificationReceivedListener(() => {
      // Notification shown automatically by setNotificationHandler
    });

    // Background/killed notification tap → deep link
    responseListener.current = addNotificationResponseReceivedListener(
      handleNotificationResponse,
    );

    return () => {
      notificationListener.current?.remove();
      responseListener.current?.remove();
    };
  }, [isAuthenticated, handleNotificationResponse]);
}
