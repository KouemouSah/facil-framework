/**
 * GrafanaImportModal — bulk-import Grafana dashboards from the live workspace.
 *
 * Flow:
 *   1. Modal opens → triggers GET /admin/grafana/discover (cached 5 min server-side).
 *   2. Renders one row per dashboard NOT yet in dashboard_registrations.
 *   3. Admin checks rows + edits slug / category / i18n titles inline.
 *      The 3 title fields default to the Grafana dashboard.title (admin can
 *      adjust per-locale).
 *   4. Submit → POST /admin/grafana/import (per-item TX on backend).
 *   5. Results panel summarises imported / skipped (already_exists) / errors.
 *
 * Auth: backend gates on `dashboards.manage`. Configuration: requires
 * GRAFANA_BASE_URL + GRAFANA_SA_TOKEN env vars; if missing, the modal renders
 * a clear hint instead of an empty list.
 */

'use client'

import React from 'react'
import { useTranslations } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import {
  AlertCircle, CheckCircle2, Download, Loader2, X,
} from 'lucide-react'

import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'

import { useGrafanaDiscover } from '../hooks/useGrafanaDiscover'
import { useGrafanaImport } from '../hooks/useGrafanaImport'
import type {
  DashboardCategory, GrafanaDiscoverEntry, GrafanaImportItem,
} from '../types'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/** Slugify a Grafana title to a valid dashboard_id (3-40 lowercase + - _). */
function toSlug(title: string, uid: string): string {
  const fromUid = uid.toLowerCase().replace(/^facil-/, '')
  if (fromUid && /^[a-z][a-z0-9_-]{2,39}$/.test(fromUid)) return fromUid
  const cleaned = title
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return cleaned.slice(0, 40) || `grafana-${uid.slice(0, 8)}`
}

interface RowState {
  selected: boolean
  dashboard_id: string
  title_es: string
  title_fr: string
  title_en: string
  category: DashboardCategory | ''
  rls_mode: 'public' | 'authenticated' | 'admin_only'
}

const CATEGORIES: DashboardCategory[] = [
  'executive', 'finance', 'operations', 'security', 'business', 'product',
]

export function GrafanaImportModal({ open, onOpenChange }: Props) {
  const t = useTranslations('admin.dashboards.import')
  const { toast } = useToast()
  const discover = useGrafanaDiscover(open)
  const importMutation = useGrafanaImport()
  const [rows, setRows] = React.useState<Record<string, RowState>>({})

  const dashboards: GrafanaDiscoverEntry[] = discover.data?.dashboards ?? []
  const importable = dashboards.filter((d) => !d.already_imported)

  // Initialise row state when discover lands.
  React.useEffect(() => {
    if (importable.length === 0) return
    setRows((prev) => {
      const next: Record<string, RowState> = { ...prev }
      for (const d of importable) {
        if (next[d.uid]) continue
        const slug = toSlug(d.title, d.uid)
        next[d.uid] = {
          selected: false,
          dashboard_id: slug,
          title_es: d.title,
          title_fr: d.title,
          title_en: d.title,
          category: '',
          rls_mode: 'authenticated',
        }
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discover.data])

  const updateRow = (uid: string, patch: Partial<RowState>) => {
    setRows((prev) => ({ ...prev, [uid]: { ...prev[uid], ...patch } }))
  }

  const selectedCount = Object.values(rows).filter((r) => r.selected).length
  const allSelected = importable.length > 0 && selectedCount === importable.length
  const toggleAll = () => {
    setRows((prev) => {
      const next = { ...prev }
      for (const d of importable) {
        if (next[d.uid]) next[d.uid] = { ...next[d.uid], selected: !allSelected }
      }
      return next
    })
  }

  const onSubmit = () => {
    const items: GrafanaImportItem[] = importable
      .filter((d) => rows[d.uid]?.selected)
      .map((d) => {
        const r = rows[d.uid]
        return {
          uid: d.uid,
          dashboard_id: r.dashboard_id,
          title_es: r.title_es,
          title_fr: r.title_fr,
          title_en: r.title_en,
          category: r.category || null,
          rls_mode: r.rls_mode,
          grafana_org_id: 1,
          display_order: 50,
        }
      })

    if (items.length === 0) return

    importMutation.mutate(
      { items },
      {
        onSuccess: (data) => {
          toast({
            title: t('toast.successTitle'),
            description: t('toast.successDesc', {
              imported: data.imported.length,
              skipped: data.skipped.length,
              errors: data.errors.length,
            }),
          })
          if (data.errors.length === 0 && data.skipped.length === 0) {
            onOpenChange(false)
          }
        },
        onError: (err: unknown) => {
          const detail =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            t('toast.errorDesc')
          toast({
            variant: 'destructive',
            title: t('toast.errorTitle'),
            description: detail,
          })
        },
      },
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            {t('title')}
          </DialogTitle>
          <DialogDescription>{t('description')}</DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto space-y-3 pr-1">
          {discover.isLoading && (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full" />)}
            </div>
          )}

          {!discover.isLoading && discover.data?.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t('errorTitle')}</AlertTitle>
              <AlertDescription className="space-y-2">
                <p>{discover.data.error}</p>
                {!discover.data.sa_token_configured && (
                  <p className="text-xs">{t('errorHelpToken')}</p>
                )}
              </AlertDescription>
            </Alert>
          )}

          {!discover.isLoading && !discover.data?.error && importable.length === 0 && (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>{t('emptyTitle')}</AlertTitle>
              <AlertDescription>
                {t('emptyDesc', { total: dashboards.length })}
              </AlertDescription>
            </Alert>
          )}

          {!discover.isLoading && !discover.data?.error && importable.length > 0 && (
            <>
              <div className="flex items-center justify-between text-sm border-b pb-2">
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={allSelected}
                    onCheckedChange={toggleAll}
                    aria-label={t('selectAll')}
                  />
                  <span className="text-muted-foreground">
                    {t('foundCount', {
                      found: importable.length,
                      total: dashboards.length,
                    })}
                  </span>
                </div>
                <span className="text-muted-foreground">
                  {t('selectedCount', { count: selectedCount })}
                </span>
              </div>

              <div className="space-y-2">
                {importable.map((d) => {
                  const r = rows[d.uid]
                  if (!r) return null
                  return (
                    <div
                      key={d.uid}
                      className="rounded-md border p-3 space-y-2 bg-card"
                    >
                      <div className="flex items-start gap-3">
                        <Checkbox
                          checked={r.selected}
                          onCheckedChange={(v) =>
                            updateRow(d.uid, { selected: !!v })
                          }
                          className="mt-1"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium">{d.title}</span>
                            <Badge variant="outline" className="font-mono text-xs">
                              {d.uid}
                            </Badge>
                            {d.folder_title && (
                              <Badge variant="secondary" className="text-xs">
                                {d.folder_title}
                              </Badge>
                            )}
                            {d.tags.slice(0, 3).map((tag) => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>

                          {r.selected && (
                            <div className="mt-3 grid gap-2 sm:grid-cols-2">
                              <div className="sm:col-span-2">
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.slug')}
                                </label>
                                <Input
                                  value={r.dashboard_id}
                                  onChange={(e) =>
                                    updateRow(d.uid, { dashboard_id: e.target.value })
                                  }
                                  className="font-mono text-sm h-8 mt-0.5"
                                  pattern="^[a-z][a-z0-9_-]{2,39}$"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.titleEs')}
                                </label>
                                <Input
                                  value={r.title_es}
                                  onChange={(e) =>
                                    updateRow(d.uid, { title_es: e.target.value })
                                  }
                                  className="text-sm h-8 mt-0.5"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.titleFr')}
                                </label>
                                <Input
                                  value={r.title_fr}
                                  onChange={(e) =>
                                    updateRow(d.uid, { title_fr: e.target.value })
                                  }
                                  className="text-sm h-8 mt-0.5"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.titleEn')}
                                </label>
                                <Input
                                  value={r.title_en}
                                  onChange={(e) =>
                                    updateRow(d.uid, { title_en: e.target.value })
                                  }
                                  className="text-sm h-8 mt-0.5"
                                />
                              </div>
                              <div>
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.category')}
                                </label>
                                <Select
                                  value={r.category || 'none'}
                                  onValueChange={(v) =>
                                    updateRow(d.uid, {
                                      category: v === 'none' ? '' : (v as DashboardCategory),
                                    })
                                  }
                                >
                                  <SelectTrigger className="h-8 mt-0.5">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="none">{t('field.none')}</SelectItem>
                                    {CATEGORIES.map((c) => (
                                      <SelectItem key={c} value={c}>
                                        {t(`category.${c}`)}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                              <div>
                                <label className="text-xs font-medium text-muted-foreground">
                                  {t('field.rlsMode')}
                                </label>
                                <Select
                                  value={r.rls_mode}
                                  onValueChange={(v) =>
                                    updateRow(d.uid, { rls_mode: v as RowState['rls_mode'] })
                                  }
                                >
                                  <SelectTrigger className="h-8 mt-0.5">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="public">{t('rls.public')}</SelectItem>
                                    <SelectItem value="authenticated">
                                      {t('rls.authenticated')}
                                    </SelectItem>
                                    <SelectItem value="admin_only">
                                      {t('rls.adminOnly')}
                                    </SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </>
          )}

          {importMutation.data && (
            <Alert variant={importMutation.data.errors.length > 0 ? 'destructive' : 'default'}>
              <CheckCircle2 className="h-4 w-4" />
              <AlertTitle>{t('result.title')}</AlertTitle>
              <AlertDescription className="space-y-1 text-xs">
                {importMutation.data.imported.length > 0 && (
                  <div className="text-emerald-600">
                    ✓ {t('result.imported', { count: importMutation.data.imported.length })}: {' '}
                    {importMutation.data.imported.join(', ')}
                  </div>
                )}
                {importMutation.data.skipped.length > 0 && (
                  <div className="text-amber-600">
                    ⊘ {t('result.skipped', { count: importMutation.data.skipped.length })}: {' '}
                    {importMutation.data.skipped.map((s) => s.dashboard_id).join(', ')}
                  </div>
                )}
                {importMutation.data.errors.length > 0 && (
                  <div className="text-destructive">
                    ✗ {t('result.errors', { count: importMutation.data.errors.length })}: {' '}
                    {importMutation.data.errors.map((e) => `${e.dashboard_id}: ${e.error}`).join('; ')}
                  </div>
                )}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            <X className="mr-2 h-4 w-4" />
            {t('close')}
          </Button>
          <Button
            onClick={onSubmit}
            disabled={selectedCount === 0 || importMutation.isPending}
          >
            {importMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('importing')}
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                {t('importBtn', { count: selectedCount })}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
