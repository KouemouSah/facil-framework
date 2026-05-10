/**
 * ActionConfirmCard - Inline confirmation card for agent-proposed actions
 *
 * Renders inside the chat when the agent proposes a Level 1+ action.
 * Shows action summary, readiness score, missing docs warning,
 * and Confirm/Reject buttons.
 *
 * @module user-documents/components
 */

'use client';

import { useTranslations } from 'next-intl';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  CalendarCheck,
  RotateCcw,
  Loader2,
  Sparkles,
} from 'lucide-react';
import type { ReadinessResult } from '../types';

// =============================================================================
// TYPES
// =============================================================================

export interface ActionConfirmCardAction {
  type: string; // 'prepare_renewal', 'prepare_request', 'suggest_appointment'
  document_name?: string;
  workflow_code?: string;
  readiness?: ReadinessResult;
  message: string;
  requires_confirmation: boolean;
}

export interface ActionConfirmCardProps {
  action: ActionConfirmCardAction;
  onConfirm: () => void;
  onReject: () => void;
  isLoading?: boolean;
}

// =============================================================================
// HELPERS
// =============================================================================

/** Icon for the action type */
function getActionIcon(type: string) {
  switch (type) {
    case 'prepare_renewal':
      return RotateCcw;
    case 'prepare_request':
      return FileText;
    case 'suggest_appointment':
      return CalendarCheck;
    default:
      return Sparkles;
  }
}

/** Color scheme for readiness score */
function getScoreColor(score: number): string {
  if (score >= 80) return 'text-green-600 dark:text-green-400';
  if (score >= 50) return 'text-orange-600 dark:text-orange-400';
  return 'text-red-600 dark:text-red-400';
}

function getProgressColor(score: number): string {
  if (score >= 80) return '[&>div]:bg-green-500';
  if (score >= 50) return '[&>div]:bg-orange-500';
  return '[&>div]:bg-red-500';
}

// =============================================================================
// COMPONENT
// =============================================================================

export function ActionConfirmCard({
  action,
  onConfirm,
  onReject,
  isLoading = false,
}: ActionConfirmCardProps) {
  const t = useTranslations('userDocuments.agent');
  const ActionIcon = getActionIcon(action.type);
  const readiness = action.readiness;
  const score = readiness?.readiness_score ?? 0;
  const hasMissing = readiness && readiness.missing_count > 0;

  return (
    <Card className="border-primary/20 bg-primary/5 my-2 overflow-hidden">
      <CardContent className="p-4 space-y-3">
        {/* ── Header ───────────────────────────────────────── */}
        <div className="flex items-start gap-3">
          <div className="shrink-0 w-8 h-8 rounded-md bg-primary/10 flex items-center justify-center">
            <ActionIcon className="h-4 w-4 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium leading-snug">
              {action.message}
            </p>
            {action.document_name && (
              <Badge variant="secondary" className="mt-1 text-xs">
                {action.document_name}
              </Badge>
            )}
          </div>
        </div>

        {/* ── Readiness Score ──────────────────────────────── */}
        {readiness && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {t('confidence')}
              </span>
              <span className={`text-xs font-semibold ${getScoreColor(score)}`}>
                {score}%
              </span>
            </div>
            <Progress
              value={score}
              className={`h-1.5 ${getProgressColor(score)}`}
            />

            {/* Ready / Missing counts */}
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-500" />
                {readiness.available}/{readiness.total_required}
              </span>
              {readiness.missing_count > 0 && (
                <span className="flex items-center gap-1 text-orange-600 dark:text-orange-400">
                  <AlertTriangle className="h-3 w-3" />
                  {readiness.missing_count} missing
                </span>
              )}
            </div>
          </div>
        )}

        {/* ── Missing Documents Warning ────────────────────── */}
        {hasMissing && readiness.missing.length > 0 && (
          <div className="rounded-md bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800/50 p-2.5">
            <p className="text-xs font-medium text-orange-800 dark:text-orange-300 mb-1 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              Documents manquants
            </p>
            <ul className="space-y-0.5">
              {readiness.missing.map((item) => (
                <li
                  key={item.code}
                  className="text-xs text-orange-700 dark:text-orange-400 pl-4 relative before:content-[''] before:absolute before:left-1.5 before:top-1.5 before:w-1 before:h-1 before:rounded-full before:bg-orange-400"
                >
                  {item.name}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* ── Action Buttons ───────────────────────────────── */}
        {action.requires_confirmation && (
          <div className="flex items-center gap-2 pt-1">
            <Button
              size="sm"
              className="flex-1 bg-green-600 hover:bg-green-700 text-white"
              onClick={onConfirm}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
              )}
              {t('confirm')}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="flex-1 border-destructive/50 text-destructive hover:bg-destructive/10"
              onClick={onReject}
              disabled={isLoading}
            >
              <XCircle className="h-3.5 w-3.5 mr-1.5" />
              {t('reject')}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
