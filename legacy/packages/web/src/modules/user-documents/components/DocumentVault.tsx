/**
 * DocumentVault - Main "Mes Documents" page with 4 tabs
 *
 * Tabs:
 * 1. Personnels   - PersonalDocumentsGrid (uploaded + wizard-imported)
 * 2. Generes      - GeneratedDocumentsGrid (certificates, receipts, etc.)
 * 3. Alertes      - AlertsTab (expiry, missing, proactive alerts)
 * 4. Preparation  - ReadinessCheck (workflow readiness cards)
 *
 * Design:
 * - Header with title, upload button, quota indicator
 * - Stats summary bar (total, personal, generated, expiring, quota)
 * - Responsive tabs filling available height (no main-page scroll)
 * - Mobile-first, tabs stack labels on small screens
 *
 * @module user-documents/components
 */

'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Upload,
  FileText,
  Shield,
  Bell,
  CheckCircle,
  FolderOpen,
  AlertTriangle,
  HardDrive,
  Settings2,
} from 'lucide-react';
import { useDocumentStats, useDocumentAlerts } from '../hooks';
import { PersonalDocumentsGrid } from './PersonalDocumentsGrid';
import { GeneratedDocumentsGrid } from './GeneratedDocumentsGrid';
import { AlertsTab } from './AlertsTab';
import { ReadinessCheck } from './ReadinessCheck';
import { DocumentUploadDialog } from './DocumentUploadDialog';
import { AgentOnboarding } from './AgentOnboarding';
import { AgentSettingsPanel } from './AgentSettingsPanel';

// ---------------------------------------------------------------------------
// Stats Card sub-component
// ---------------------------------------------------------------------------

interface StatsCardProps {
  icon: typeof FileText;
  label: string;
  value: number | string;
  subValue?: string;
  variant?: 'default' | 'warning' | 'danger';
  isLoading?: boolean;
}

function StatsCard({
  icon: Icon,
  label,
  value,
  subValue,
  variant = 'default',
  isLoading = false,
}: StatsCardProps) {
  const colorMap = {
    default: 'text-foreground',
    warning: 'text-orange-600 dark:text-orange-400',
    danger: 'text-red-600 dark:text-red-400',
  };

  return (
    <Card className="border bg-card">
      <CardContent className="p-3 flex items-center gap-3">
        <div className="shrink-0 w-8 h-8 rounded-md bg-muted flex items-center justify-center">
          <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          {isLoading ? (
            <Skeleton className="h-5 w-10" />
          ) : (
            <p className={`text-lg font-bold leading-none ${colorMap[variant]}`}>
              {value}
            </p>
          )}
          <p className="text-[10px] text-muted-foreground truncate mt-0.5">
            {label}
          </p>
          {subValue && (
            <p className="text-[10px] text-muted-foreground">{subValue}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Quota Bar sub-component
// ---------------------------------------------------------------------------

function QuotaBar({
  usedBytes,
  maxBytes,
  percentage,
  isLoading,
}: {
  usedBytes: number;
  maxBytes: number;
  percentage: number;
  isLoading: boolean;
}) {
  const _t = useTranslations('userDocuments');

  const formatSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024)
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const getColor = (pct: number): string => {
    if (pct >= 90) return '[&>div]:bg-red-500';
    if (pct >= 70) return '[&>div]:bg-orange-500';
    return '[&>div]:bg-primary';
  };

  if (isLoading) {
    return <Skeleton className="h-4 w-full" />;
  }

  return (
    <div className="flex items-center gap-3">
      <HardDrive className="h-4 w-4 text-muted-foreground shrink-0" />
      <Progress value={percentage} className={`h-2 flex-1 ${getColor(percentage)}`} />
      <span className="text-xs text-muted-foreground shrink-0 whitespace-nowrap">
        {formatSize(usedBytes)} / {formatSize(maxBytes)} ({percentage}%)
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function DocumentVault() {
  const t = useTranslations('userDocuments');
  const router = useRouter();
  const searchParams = useSearchParams();
  const { data: stats, isLoading: statsLoading } = useDocumentStats();
  const { unreadCount } = useDocumentAlerts();
  // Support deep-link to tab: ?tab=generated opens generated docs tab
  const initialTab = searchParams.get('tab') || 'personal';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [uploadOpen, setUploadOpen] = useState(false);
  // Agent settings panel (opened via gear icon OR ?settings=agent deep-link)
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [highlightPerm, setHighlightPerm] = useState<string | undefined>(undefined);
  // Prevents the URL reader from re-firing on re-renders or after cleanup
  const hasHandledUrlRef = useRef(false);

  // Read deep-link query params from chatbot actions / ReadinessCheck buttons.
  // Supported params:
  //   ?settings=agent                            → open AgentSettingsPanel
  //   ?settings=agent&permission=prepare_request → also scroll/highlight the row
  //   ?upload=CODE                               → open DocumentUploadDialog
  // After consumption we strip the params via router.replace so a refresh
  // doesn't re-open the panels and the back button behaves naturally.
  useEffect(() => {
    if (hasHandledUrlRef.current) return;
    const settings = searchParams.get('settings');
    const permission = searchParams.get('permission');
    const upload = searchParams.get('upload');

    let handled = false;

    if (settings === 'agent') {
      setAgentPanelOpen(true);
      if (permission) setHighlightPerm(permission);
      handled = true;
    }

    if (upload) {
      setUploadOpen(true);
      handled = true;
    }

    if (handled) {
      hasHandledUrlRef.current = true;
      const clean = new URL(window.location.href);
      clean.searchParams.delete('settings');
      clean.searchParams.delete('permission');
      clean.searchParams.delete('upload');
      const nextSearch = clean.searchParams.toString();
      router.replace(`${clean.pathname}${nextSearch ? `?${nextSearch}` : ''}`, { scroll: false });
    }
  }, [searchParams, router]);

  return (
    <div className="flex flex-col h-full gap-4 p-4 md:p-6">
      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t('title')}
          </h1>
          <p className="text-muted-foreground text-sm">
            {t('subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setAgentPanelOpen(true)}
            aria-label={t('agent.settings')}
            title={t('agent.settings')}
          >
            <Settings2 className="h-4 w-4" strokeWidth={1.5} />
          </Button>
          <Button onClick={() => setUploadOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            {t('addDocument')}
          </Button>
        </div>
      </div>

      {/* ── Stats Summary Bar ──────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatsCard
          icon={FolderOpen}
          label={t('stats.total')}
          value={stats?.total_active ?? 0}
          isLoading={statsLoading}
        />
        <StatsCard
          icon={FileText}
          label={t('stats.personal')}
          value={stats?.personal_count ?? 0}
          subValue={
            stats?.wizard_count
              ? t('stats.wizardImported', { count: stats.wizard_count })
              : undefined
          }
          isLoading={statsLoading}
        />
        <StatsCard
          icon={Shield}
          label={t('stats.generated')}
          value={stats?.generated_count ?? 0}
          isLoading={statsLoading}
        />
        <StatsCard
          icon={AlertTriangle}
          label={t('stats.expiring')}
          value={(stats?.expired_count ?? 0) + (stats?.expiring_count ?? 0)}
          variant={
            (stats?.expired_count ?? 0) > 0
              ? 'danger'
              : (stats?.expiring_count ?? 0) > 0
                ? 'warning'
                : 'default'
          }
          isLoading={statsLoading}
        />
        <div className="col-span-2 md:col-span-1 flex items-center">
          <div className="w-full">
            <QuotaBar
              usedBytes={stats?.quota_used_bytes ?? 0}
              maxBytes={stats?.quota_max_bytes ?? 1}
              percentage={stats?.quota_percentage ?? 0}
              isLoading={statsLoading}
            />
          </div>
        </div>
      </div>

      {/* ── Tabs ───────────────────────────────────────────── */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="flex-1 flex flex-col min-h-0"
      >
        <TabsList className="grid grid-cols-4 w-full max-w-lg">
          <TabsTrigger value="personal" className="gap-1 text-xs sm:text-sm">
            <FileText className="h-4 w-4 hidden sm:inline-block" />
            {t('tabs.personal')}
          </TabsTrigger>
          <TabsTrigger value="generated" className="gap-1 text-xs sm:text-sm">
            <Shield className="h-4 w-4 hidden sm:inline-block" />
            {t('tabs.generated')}
          </TabsTrigger>
          <TabsTrigger value="alerts" className="gap-1 text-xs sm:text-sm">
            <Bell className="h-4 w-4 hidden sm:inline-block" />
            {t('tabs.alerts')}
            {unreadCount > 0 && (
              <Badge
                variant="destructive"
                className="ml-1 h-5 min-w-[20px] px-1 text-[10px]"
              >
                {unreadCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="readiness" className="gap-1 text-xs sm:text-sm">
            <CheckCircle className="h-4 w-4 hidden sm:inline-block" />
            {t('tabs.readiness')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="personal" className="flex-1 mt-4 min-h-0">
          <PersonalDocumentsGrid />
        </TabsContent>
        <TabsContent value="generated" className="flex-1 mt-4 min-h-0">
          <GeneratedDocumentsGrid />
        </TabsContent>
        <TabsContent value="alerts" className="flex-1 mt-4 min-h-0">
          <AlertsTab />
        </TabsContent>
        <TabsContent value="readiness" className="flex-1 mt-4 min-h-0">
          <ReadinessCheck />
        </TabsContent>
      </Tabs>

      {/* ── Upload Dialog ──────────────────────────────────── */}
      {uploadOpen && (
        <DocumentUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      )}

      {/* ── First-visit Onboarding ───────────────────────── */}
      <AgentOnboarding />

      {/* ── Agent Settings Panel (gear icon or ?settings=agent deep-link) ── */}
      <AgentSettingsPanel
        open={agentPanelOpen}
        onOpenChange={(open) => {
          setAgentPanelOpen(open);
          if (!open) setHighlightPerm(undefined);
        }}
        initialHighlightPermission={highlightPerm}
      />
    </div>
  );
}
