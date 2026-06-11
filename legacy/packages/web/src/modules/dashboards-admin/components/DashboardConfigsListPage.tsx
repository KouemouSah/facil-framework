/**
 * DashboardConfigsListPage — wraps the admin /dashboards/config view.
 *
 * Mig 323 (2026-05-05):
 * - Toolbar: "Importer depuis Grafana" button (opens GrafanaImportModal)
 * - Delete action per row (soft-delete)
 * - Now shows ALL dashboards in dashboard_registrations (not just 3)
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import {
  AlertCircle, Download, Lock, Settings, Trash2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { useToast } from '@/hooks/use-toast'

import { useDashboardConfigs } from '../hooks/useDashboardConfigs'
import { useDeleteDashboardConfig } from '../hooks/useDeleteDashboardConfig'
import { DashboardConfigForm } from './DashboardConfigForm'
import { GrafanaImportModal } from './GrafanaImportModal'
import type { DashboardConfigDTO } from '../types'

interface DeleteRowButtonProps {
  config: DashboardConfigDTO
}

function DeleteRowButton({ config }: DeleteRowButtonProps) {
  const t = useTranslations('admin.dashboards.config')
  const { toast } = useToast()
  const deleteMutation = useDeleteDashboardConfig()

  const onConfirm = () => {
    deleteMutation.mutate(config.dashboard_id, {
      onSuccess: () => {
        toast({
          title: t('delete.successTitle'),
          description: config.label,
        })
      },
      onError: (err: unknown) => {
        const detail =
          (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          t('delete.errorDesc')
        toast({
          variant: 'destructive',
          title: t('delete.errorTitle'),
          description: detail,
        })
      },
    })
  }

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="text-destructive hover:bg-destructive/10"
          disabled={!config.is_active || deleteMutation.isPending}
          aria-label={t('delete.action')}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('delete.confirmTitle')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t('delete.confirmBody', { label: config.label })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>{t('delete.cancel')}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {t('delete.confirm')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function DashboardConfigsListPage() {
  const t = useTranslations('admin.dashboards.config')
  const { data, isLoading, error } = useDashboardConfigs()
  const [importOpen, setImportOpen] = React.useState(false)

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => <Skeleton key={i} className="h-72 w-full" />)}
      </div>
    )
  }

  if (error) {
    const status = (error as { response?: { status?: number } })?.response?.status
    if (status === 403) {
      return (
        <Alert variant="destructive">
          <Lock className="h-4 w-4" />
          <AlertTitle>{t('forbiddenTitle')}</AlertTitle>
          <AlertDescription>{t('forbiddenHelp')}</AlertDescription>
        </Alert>
      )
    }
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t('errorTitle')}</AlertTitle>
        <AlertDescription>
          {(error as Error)?.message ?? t('errorGeneric')}
        </AlertDescription>
      </Alert>
    )
  }

  const configs = data?.configs ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm text-muted-foreground">
          {t('listSummary', {
            total: configs.length,
            active: configs.filter((c) => c.is_active).length,
          })}
        </div>
        <Button onClick={() => setImportOpen(true)} className="gap-2">
          <Download className="h-4 w-4" />
          {t('importGrafanaBtn')}
        </Button>
      </div>

      <GrafanaImportModal open={importOpen} onOpenChange={setImportOpen} />

      {configs.length === 0 ? (
        <Alert>
          <Settings className="h-4 w-4" />
          <AlertTitle>{t('emptyTitle')}</AlertTitle>
          <AlertDescription>{t('emptyHelp')}</AlertDescription>
        </Alert>
      ) : (
        <div className="space-y-4">
          {configs.map((config) => (
            <div key={config.dashboard_id} className="relative">
              <div className="absolute right-4 top-4 z-10">
                <DeleteRowButton config={config} />
              </div>
              <DashboardConfigForm config={config} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
