/**
 * ProactiveNotificationCard - Banner card for agent proactive suggestions
 *
 * Shows when the agent has prepared something proactively (e.g. renewal, request).
 * Can appear at top of dashboard or inside chat. Actions: View / Later / Don't suggest.
 *
 * @module user-documents/components
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Sparkles,
  Eye,
  Clock,
  BellOff,
  X,
  RotateCcw,
  FileText,
  CalendarCheck,
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export interface ProactiveNotification {
  id: string;
  type: 'renewal_prepared' | 'request_prepared' | 'appointment_suggested';
  document_name?: string;
  workflow_code?: string;
  message: string;
  created_at: string;
}

export interface ProactiveNotificationCardProps {
  notification: ProactiveNotification;
  onView: (notification: ProactiveNotification) => void;
  onLater: (notification: ProactiveNotification) => void;
  onDontSuggest: (notification: ProactiveNotification) => void;
}

// =============================================================================
// HELPERS
// =============================================================================

function getNotificationIcon(type: ProactiveNotification['type']) {
  switch (type) {
    case 'renewal_prepared':
      return RotateCcw;
    case 'request_prepared':
      return FileText;
    case 'appointment_suggested':
      return CalendarCheck;
    default:
      return Sparkles;
  }
}

function getNotificationVariant(type: ProactiveNotification['type']): string {
  switch (type) {
    case 'renewal_prepared':
      return 'border-blue-200 bg-blue-50 dark:border-blue-800/50 dark:bg-blue-950/30';
    case 'request_prepared':
      return 'border-green-200 bg-green-50 dark:border-green-800/50 dark:bg-green-950/30';
    case 'appointment_suggested':
      return 'border-purple-200 bg-purple-50 dark:border-purple-800/50 dark:bg-purple-950/30';
    default:
      return '';
  }
}

function getIconColor(type: ProactiveNotification['type']): string {
  switch (type) {
    case 'renewal_prepared':
      return 'text-blue-600 dark:text-blue-400';
    case 'request_prepared':
      return 'text-green-600 dark:text-green-400';
    case 'appointment_suggested':
      return 'text-purple-600 dark:text-purple-400';
    default:
      return 'text-primary';
  }
}

// =============================================================================
// COMPONENT
// =============================================================================

export function ProactiveNotificationCard({
  notification,
  onView,
  onLater,
  onDontSuggest,
}: ProactiveNotificationCardProps) {
  const t = useTranslations('userDocuments.agent');
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const Icon = getNotificationIcon(notification.type);
  const variantClasses = getNotificationVariant(notification.type);
  const iconColor = getIconColor(notification.type);

  const handleDontSuggest = () => {
    setDismissed(true);
    onDontSuggest(notification);
  };

  const handleLater = () => {
    setDismissed(true);
    onLater(notification);
  };

  return (
    <Alert className={`relative pr-10 ${variantClasses}`}>
      {/* ── Close Button ───────────────────────────────────── */}
      <button
        type="button"
        onClick={handleLater}
        className="absolute right-2 top-2 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        aria-label="Close"
      >
        <X className="h-4 w-4" />
      </button>

      {/* ── Icon ───────────────────────────────────────────── */}
      <div className={`shrink-0 ${iconColor}`}>
        <Icon className="h-4 w-4" />
      </div>

      {/* ── Content ────────────────────────────────────────── */}
      <AlertTitle className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold">
          {t('proactive.prepared')}
        </span>
        {notification.document_name && (
          <Badge variant="secondary" className="text-[10px] h-4 px-1.5">
            {notification.document_name}
          </Badge>
        )}
      </AlertTitle>
      <AlertDescription className="text-xs leading-relaxed mb-3">
        {notification.message}
      </AlertDescription>

      {/* ── Actions ────────────────────────────────────────── */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="default"
          className="h-7 text-xs"
          onClick={() => onView(notification)}
        >
          <Eye className="h-3 w-3 mr-1" />
          {t('proactive.view')}
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-xs"
          onClick={handleLater}
        >
          <Clock className="h-3 w-3 mr-1" />
          {t('proactive.later')}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 text-xs text-muted-foreground"
          onClick={handleDontSuggest}
        >
          <BellOff className="h-3 w-3 mr-1" />
          {t('proactive.dontSuggest')}
        </Button>
      </div>
    </Alert>
  );
}
