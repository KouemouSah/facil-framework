'use client';

/**
 * Card component for a single extracted identifier
 * Shows type, value, document source, confidence, expiration, and action buttons
 */

import { useTranslations } from 'next-intl';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { VerificationStatusBadge } from './VerificationStatusBadge';
import { cn } from '@/lib/utils';
import type { ExtractedIdentifier } from '../types';
import {
  CheckCircle,
  XCircle,
  FileText,
  Calendar,
  Percent,
  AlertTriangle,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface IdentifierCardProps {
  identifier: ExtractedIdentifier;
  onVerify?: () => void;
  onReject?: () => void;
  isLoading?: boolean;
  className?: string;
}

export function IdentifierCard({
  identifier,
  onVerify,
  onReject,
  isLoading = false,
  className,
}: IdentifierCardProps) {
  const t = useTranslations('verification');

  const isPending = identifier.status === 'pending';
  const isVerified =
    identifier.status === 'verified' ||
    identifier.status === 'verified_manually';
  const isRejected =
    identifier.status === 'rejected' || identifier.status === 'fraud';

  // Check expiration status
  const isExpired = identifier.expiresAt
    ? new Date(identifier.expiresAt) < new Date()
    : false;
  const expiresSoon = identifier.expiresAt
    ? new Date(identifier.expiresAt) < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000) && !isExpired
    : false;

  // Get identifier type label from translations, fallback to raw value
  const getIdentifierTypeLabel = (type: string): string => {
    try {
      return t(`identifierTypes.${type}`);
    } catch {
      return type;
    }
  };

  // Get source label from translations, fallback to raw value
  const getSourceLabel = (source: string): string => {
    try {
      return t(`sources.${source}`);
    } catch {
      return source;
    }
  };

  return (
    <Card
      className={cn(
        'transition-all',
        isPending && 'border-yellow-300 bg-yellow-50/50 dark:bg-yellow-900/10',
        isVerified && 'border-green-300 bg-green-50/50 dark:bg-green-900/10',
        isRejected && 'border-red-300 bg-red-50/50 dark:bg-red-900/10',
        className
      )}
    >
      <CardContent className="pt-4 pb-2">
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="text-sm font-medium text-muted-foreground">
              {getIdentifierTypeLabel(identifier.identifierType)}
            </p>
            <p className="text-xl font-mono font-semibold tracking-wider">
              {identifier.value}
            </p>
          </div>
          <VerificationStatusBadge status={identifier.status} />
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            <span className="truncate">{identifier.documentName}</span>
          </div>

          {identifier.confidence !== null && (
            <div className="flex items-center gap-1.5">
              <Percent className="h-3.5 w-3.5" />
              <span>{Math.round(identifier.confidence * 100)}% {t('card.confidence')}</span>
            </div>
          )}

          {identifier.expiresAt && (
            <div className={cn(
              "flex items-center gap-1.5 col-span-2",
              isExpired && "text-red-600 font-medium",
              expiresSoon && !isExpired && "text-orange-500"
            )}>
              {isExpired ? (
                <AlertTriangle className="h-3.5 w-3.5" />
              ) : (
                <Calendar className="h-3.5 w-3.5" />
              )}
              <span>
                {t('card.expiresAt')}:{' '}
                {new Date(identifier.expiresAt).toLocaleDateString()}
              </span>
              {isExpired && (
                <Badge variant="destructive" className="ml-1 text-xs">
                  {t('card.expired')}
                </Badge>
              )}
              {expiresSoon && !isExpired && (
                <Badge variant="outline" className="ml-1 text-xs border-orange-400 text-orange-500">
                  {t('card.expiresSoon')}
                </Badge>
              )}
            </div>
          )}

          {identifier.verifiedAt && (
            <div className="flex items-center gap-1.5 col-span-2 text-green-600">
              <CheckCircle className="h-3.5 w-3.5" />
              <span>
                {t('card.verifiedAt')}:{' '}
                {new Date(identifier.verifiedAt).toLocaleDateString()}
                {identifier.source && ` (${getSourceLabel(identifier.source)})`}
              </span>
            </div>
          )}
        </div>
      </CardContent>

      {isPending && (onVerify || onReject) && (
        <CardFooter className="pt-2 pb-4 gap-2">
          {onVerify && (
            <Button
              size="sm"
              onClick={onVerify}
              disabled={isLoading}
              className="flex-1 bg-green-600 hover:bg-green-700"
            >
              <CheckCircle className="h-4 w-4 mr-1.5" />
              {t('actions.verify')}
            </Button>
          )}
          {onReject && (
            <Button
              size="sm"
              variant="destructive"
              onClick={onReject}
              disabled={isLoading}
              className="flex-1"
            >
              <XCircle className="h-4 w-4 mr-1.5" />
              {t('actions.reject')}
            </Button>
          )}
        </CardFooter>
      )}
    </Card>
  );
}
