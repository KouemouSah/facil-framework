'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { getAuthData, clearAllAuthData } from '@/core/auth/storage';
import { usePathname } from 'next/navigation';
import { useTranslations } from 'next-intl';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import apiClient from '@/core/api/client';

const IDLE_WARNING_MS = 25 * 60 * 1000; // Show warning at 25 min of idle
const IDLE_LOGOUT_MS = 30 * 60 * 1000;  // Force logout at 30 min
const EVENTS = ['mousedown', 'keydown', 'touchstart', 'scroll'] as const;

export function SessionTimeoutDialog() {
  const [showWarning, setShowWarning] = useState(false);
  const [countdown, setCountdown] = useState(300); // 5 min in seconds
  const lastActivityRef = useRef(Date.now());
  const warningTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const logoutTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const countdownRef = useRef<ReturnType<typeof setInterval>>();
  const pathname = usePathname();
  const t = useTranslations('dashboard');

  // Only run on dashboard (authenticated) pages
  const isAuthPage = pathname?.includes('/auth');
  const isPublicPage = pathname === '/' || pathname?.match(/^\/(es|fr|en)\/?$/);

  const handleForceLogout = useCallback(() => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    clearAllAuthData();
    const pathParts = window.location.pathname.split('/');
    const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es';
    window.location.href = `/${locale}/auth?reason=timeout`;
  }, []);

  const resetTimers = useCallback(() => {
    lastActivityRef.current = Date.now();
    setShowWarning(false);

    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    warningTimerRef.current = setTimeout(() => {
      const authData = getAuthData();
      if (!authData?.access_token) return;
      setShowWarning(true);
      setCountdown(300);

      countdownRef.current = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            handleForceLogout();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, IDLE_WARNING_MS);

    logoutTimerRef.current = setTimeout(() => {
      handleForceLogout();
    }, IDLE_LOGOUT_MS);
  }, [handleForceLogout]);

  const handleExtendSession = useCallback(async () => {
    try {
      // Ping the backend to refresh the session
      await apiClient.get('/auth/me');
    } catch {
      // If it fails, token refresh interceptor will handle it
    }
    resetTimers();
  }, [resetTimers]);

  useEffect(() => {
    if (isAuthPage || isPublicPage) return;
    const authData = getAuthData();
    if (!authData?.access_token) return;

    resetTimers();

    const onActivity = () => {
      if (!showWarning) resetTimers();
    };

    EVENTS.forEach((event) => window.addEventListener(event, onActivity, { passive: true }));

    return () => {
      EVENTS.forEach((event) => window.removeEventListener(event, onActivity));
      if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isAuthPage, isPublicPage, resetTimers, showWarning]);

  if (isAuthPage || isPublicPage || !showWarning) return null;

  const minutes = Math.floor(countdown / 60);
  const seconds = countdown % 60;
  const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;

  return (
    <AlertDialog open={showWarning}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('sessionAboutToExpire')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t.rich('sessionExpiresIn', {
              time: () => (
                <span className="font-bold text-orange-600">{timeStr}</span>
              ),
            })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <Button variant="outline" onClick={handleForceLogout}>
            {t('sessionLogout')}
          </Button>
          <Button onClick={handleExtendSession}>
            {t('sessionContinue')}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
