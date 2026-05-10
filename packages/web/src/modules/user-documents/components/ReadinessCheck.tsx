/**
 * ReadinessCheck - Workflow document readiness cards
 *
 * Shows a card per workflow with:
 * - Readiness score (progress ring or bar)
 * - List of ready, missing, and expiring documents
 * - "Can start" indicator
 * - Link to start the procedure
 *
 * @module user-documents/components
 */

'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Rocket,
  FileSearch,
  ArrowRight,
  MessageSquare,
  FolderOpen,
  BookOpen,
  Car,
  FileText,
  Home,
  Search,
  Copy,
  Award,
  CreditCard,
  CheckCircle2,
  Plane,
  FilePlus,
  Building2,
  ClipboardList,
  Upload,
  type LucideIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { userDocumentsApi } from '../services/api';
import { userDocumentKeys } from '../hooks/useUserDocuments';
import type { ReadinessResult, ReadinessItem } from '../types';

// ---------------------------------------------------------------------------
// Workflow display metadata
// ---------------------------------------------------------------------------

const WORKFLOW_ICONS: Record<string, LucideIcon> = {
  PASAPORTE_EXPEDICION: BookOpen,
  PASAPORTE_RENOVACION: BookOpen,
  LICENCIA_CONDUCIR: Car,
  CONTRATO_ONRC: ClipboardList,
  RESIDENCIA: Home,
  MATRICULACION_DGT: Car,
  INSPECCION_ITVE: Search,
  DUPLICADO_VEHICULO: Copy,
  PROMOCION_ADMIN: Award,
  CARNET_FUNCIONARIO: CreditCard,
  VERIFICACION: CheckCircle2,
  TRAMITES_VISADO: Plane,
  PERMISO_EXTRAORDINARIO: FilePlus,
  CERTIFICADO_ADMIN: Building2,
};

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

// ---------------------------------------------------------------------------
// Readiness Item Row
// ---------------------------------------------------------------------------

function ReadinessItemRow({
  item,
  status,
}: {
  item: ReadinessItem;
  status: 'ready' | 'missing' | 'expiring';
}) {
  const locale = useLocale();
  const t = useTranslations('userDocuments');
  const iconMap = {
    ready: <CheckCircle className="h-3.5 w-3.5 text-green-600 dark:text-green-400 shrink-0" />,
    missing: <XCircle className="h-3.5 w-3.5 text-red-500 shrink-0" />,
    expiring: <AlertTriangle className="h-3.5 w-3.5 text-orange-500 shrink-0" />,
  };

  return (
    <div className="flex items-center gap-2 py-1">
      {iconMap[status]}
      <span className="text-xs flex-1 truncate">{item.name}</span>
      {status === 'missing' && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-xs text-primary"
          onClick={() => {
            window.location.href = `/${locale}/dashboard/documents?upload=${encodeURIComponent(item.code)}`;
          }}
        >
          <Upload className="mr-1 h-3 w-3" strokeWidth={1.5} />
          {t('readiness.uploadNow')}
        </Button>
      )}
      {status === 'expiring' && item.days !== undefined && (
        <Badge
          variant="outline"
          className="text-[10px] px-1 h-4 bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 border-none"
        >
          {item.days}d
        </Badge>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single Readiness Card
// ---------------------------------------------------------------------------

function ReadinessCard({ result }: { result: ReadinessResult }) {
  const locale = useLocale();
  const router = useRouter();
  const t = useTranslations('userDocuments');
  const WorkflowIcon = WORKFLOW_ICONS[result.workflow_code] ?? FileText;
  const label = t(`workflows.${result.workflow_code.toLowerCase()}`, { defaultValue: result.workflow_code.replace(/_/g, ' ') });
  const scoreColor = getScoreColor(result.readiness_score);
  const progressColor = getProgressColor(result.readiness_score);

  return (
    <Card className="hover:shadow-md transition-shadow min-h-[220px]">
      <CardHeader className="pb-2 pt-4 px-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium truncate flex items-center gap-1.5">
            <WorkflowIcon className="h-4 w-4 shrink-0 text-muted-foreground" strokeWidth={1.5} />
            {label}
          </CardTitle>
          <div className="flex items-center gap-2 shrink-0">
            <span className={`text-lg font-bold ${scoreColor}`}>
              {result.readiness_score}%
            </span>
            {result.can_start && (
              <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-none text-[10px] h-5">
                <Rocket className="h-3 w-3 mr-0.5" />
                {t('readiness.canStart')}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        {/* Progress bar */}
        <Progress
          value={result.readiness_score}
          className={`h-1.5 mb-3 ${progressColor}`}
        />

        {/* Counts summary */}
        <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
          <span>
            {t('readiness.available', {
              count: result.available,
              total: result.total_required,
            })}
          </span>
          {result.missing_count > 0 && (
            <span className="text-red-500">
              {t('readiness.missing', { count: result.missing_count })}
            </span>
          )}
          {result.expiring.length > 0 && (
            <span className="text-orange-500">
              {t('readiness.expiring', { count: result.expiring.length })}
            </span>
          )}
        </div>

        {/* Ready items */}
        {result.ready.length > 0 && (
          <div className="mb-2">
            {result.ready.map((item) => (
              <ReadinessItemRow key={item.code} item={item} status="ready" />
            ))}
          </div>
        )}

        {/* Expiring items */}
        {result.expiring.length > 0 && (
          <div className="mb-2">
            {result.expiring.map((item) => (
              <ReadinessItemRow key={item.code} item={item} status="expiring" />
            ))}
          </div>
        )}

        {/* Missing items */}
        {result.missing.length > 0 && (
          <div className="mb-2">
            {result.missing.map((item) => (
              <ReadinessItemRow key={item.code} item={item} status="missing" />
            ))}
          </div>
        )}

        {/* Vault auto-fill hint */}
        {result.can_start && (
          <p className="text-[10px] text-muted-foreground mt-2">
            {t('readiness.vaultHint')}
          </p>
        )}

        {/* Action buttons */}
        <div className="flex gap-2 mt-2">
          {result.can_start && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => {
                router.push(
                  `/${locale}/dashboard/service-requests/new?workflow=${encodeURIComponent(result.workflow_code)}`,
                );
              }}
            >
              {t('readiness.startProcedure')}
              <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-primary"
            onClick={() => {
              const msg = `${t('readiness.askAssistant') || 'Prepárame la demanda de'} ${label}`;
              window.location.href = `/${locale}/dashboard/chat?q=${encodeURIComponent(msg)}`;
            }}
          >
            <MessageSquare className="mr-1 h-3 w-3" strokeWidth={1.5} />
            {t('readiness.askAssistant') || 'Assistant'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const QUICK_WORKFLOWS = [
  { code: 'PASAPORTE_NUEVO', labelKey: 'workflows.pasaporte_nuevo' },
  { code: 'PASAPORTE_RENOVACION', labelKey: 'workflows.pasaporte_renovacion' },
  { code: 'RESIDENCIA_PRIMERA_VEZ', labelKey: 'workflows.residencia_primera_vez' },
  { code: 'CONDUCIR_NUEVO', labelKey: 'workflows.conducir_nuevo' },
  { code: 'FP_CARNET_FUNCIONARIO', labelKey: 'workflows.fp_carnet_funcionario' },
  { code: 'CONTRATO_SERVICIO', labelKey: 'workflows.contrato_servicio' },
] as const;

export function ReadinessCheck() {
  const locale = useLocale();
  const t = useTranslations('userDocuments');

  // Fetch all workflows readiness in a single call (no workflowCode = all)
  const { data, isLoading, error } = useQuery<ReadinessResult[], Error>({
    queryKey: userDocumentKeys.readiness('__all__'),
    queryFn: async () => {
      const result = await userDocumentsApi.getReadiness();
      // API returns array when no specific workflow_code is provided
      return Array.isArray(result) ? result : [result];
    },
    staleTime: 60_000,
    refetchOnWindowFocus: true,
  });

  const results = data ?? [];

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Launch section */}
      <div className="mb-2 p-4 border rounded-xl bg-accent/30">
        <div className="flex items-center gap-2 mb-2">
          <Rocket className="h-5 w-5 text-primary" strokeWidth={1.5} />
          <h3 className="text-sm font-semibold">{t('readiness.launchTitle') || 'Iniciar un tramite'}</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          {t('readiness.launchDesc') || 'El asistente carga sus documentos y pre-rellena el formulario automaticamente.'}
        </p>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {QUICK_WORKFLOWS.map((wf) => {
            const wfLabel = t(wf.labelKey, { defaultValue: wf.code.replace(/_/g, ' ') });
            return (
              <Button
                key={wf.code}
                variant="outline"
                size="sm"
                className="text-xs justify-start gap-2"
                onClick={() => {
                  window.location.href = `/${locale}/dashboard/chat?q=${encodeURIComponent(`${t('readiness.askAssistant')} ${wfLabel}`)}`;
                }}
              >
                <Rocket className="h-3 w-3 text-primary" strokeWidth={1.5} />
                {wfLabel}
              </Button>
            );
          })}
        </div>
      </div>

      {/* Header info */}
      {!isLoading && results.length > 0 && (
        <div className="flex items-center gap-2">
          <FileSearch className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {t('readiness.summary', { count: results.length })}
          </span>
          {results.filter((r) => r.can_start).length > 0 && (
            <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 border-none text-xs">
              {t('readiness.readyCount', {
                count: results.filter((r) => r.can_start).length,
              })}
            </Badge>
          )}
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="rounded-lg border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-6 w-12" />
              </div>
              <Skeleton className="h-1.5 w-full" />
              <div className="space-y-2">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && results.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
          <FolderOpen className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium">{t('readiness.emptyTitle')}</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            {t('readiness.emptyDescription')}
          </p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error.message}
        </div>
      )}

      {/* Readiness cards grid */}
      {!isLoading && results.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 pb-4">
          {results
            .sort((a, b) => {
              // Sort: can_start first, then by score descending
              if (a.can_start !== b.can_start) return a.can_start ? -1 : 1;
              return b.readiness_score - a.readiness_score;
            })
            .map((result) => (
              <ReadinessCard key={result.workflow_code} result={result} />
            ))}
        </div>
      )}
    </div>
  );
}
