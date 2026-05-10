'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import {
  Sparkles, FileText, Languages, Search,
  CheckCircle, XCircle, Clock, AlertTriangle,
  RefreshCw, Loader2, ChevronRight, Pencil,
  RotateCcw, CheckCheck, Building2, Eye, EyeOff,
  Play, Zap,
} from 'lucide-react'
import { enrichmentApi } from '@/modules/enrichment/services/enrichment-api'
import type { EnrichmentStats, EnrichmentTask, EnrichmentProgress, PendingDraft, MinistryOption } from '@/modules/enrichment/types/enrichment'
import { useToast } from '@/hooks/use-toast'

// ============================================================
// Progress Bar Component — Real-time polling during processing
// ============================================================
function ProcessingProgress({
  onComplete,
  t,
}: {
  onComplete: () => void
  t: (key: string, values?: Record<string, string | number>) => string
}) {
  const [progress, setProgress] = useState<EnrichmentProgress | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const hasCompletedRef = useRef(false)

  useEffect(() => {
    // Poll every 2 seconds
    const poll = async () => {
      try {
        const p = await enrichmentApi.getProgress()
        setProgress(p)

        if (p.status === 'completed' && !hasCompletedRef.current) {
          hasCompletedRef.current = true
          // Stop polling + notify parent
          if (intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
          // Small delay to show 100% before callback
          setTimeout(onComplete, 1500)
        }
      } catch {
        // Silently ignore polling errors
      }
    }

    poll() // Immediate first poll
    intervalRef.current = setInterval(poll, 2000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [onComplete])

  if (!progress || progress.status === 'idle') return null

  const pct = progress.total > 0
    ? Math.round((progress.processed / progress.total) * 100)
    : 0

  const isRunning = progress.status === 'running' || progress.status === 'circuit_breaker_pause'
  const isComplete = progress.status === 'completed'

  return (
    <Card className={`border-2 ${isComplete ? 'border-emerald-300 bg-emerald-50/50' : 'border-blue-300 bg-blue-50/50'}`}>
      <CardContent className="pt-4 pb-3">
        <div className="flex items-center gap-2 mb-2">
          {isRunning ? (
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          ) : isComplete ? (
            <CheckCircle className="h-4 w-4 text-emerald-600" />
          ) : (
            <Zap className="h-4 w-4 text-amber-600" />
          )}
          <span className="text-sm font-medium">
            {isComplete
              ? t('processingComplete')
              : progress.status === 'circuit_breaker_pause'
                ? t('circuitBreakerPause')
                : t('processingProgress', {
                    processed: progress.processed,
                    total: progress.total,
                    pct,
                  })
            }
          </span>
          {progress.failed > 0 && (
            <Badge variant="destructive" className="text-[10px] ml-auto">
              {t('processingFailed', { failed: progress.failed })}
            </Badge>
          )}
        </div>

        <Progress
          value={isComplete ? 100 : pct}
          className="h-2"
        />

        <div className="flex items-center justify-between mt-2 text-[11px] text-muted-foreground">
          <span>{progress.processed}/{progress.total} {t('ok')}</span>
          {progress.tokensTotal > 0 && (
            <span>{t('processingTokens', { tokens: progress.tokensTotal })}</span>
          )}
        </div>

        {isComplete && (
          <p className="text-xs text-emerald-700 mt-1">
            {t('processingCompleteDesc', {
              processed: progress.processed,
              failed: progress.failed,
              tokens: progress.tokensTotal,
            })}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

// ============================================================
// Stats Cards
// ============================================================
function StatsCards({ stats, loading, t }: { stats: EnrichmentStats | null; loading: boolean; t: ReturnType<typeof import('next-intl').useTranslations> }) {
  if (loading || !stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardContent className="pt-4 pb-3">
              <div className="h-4 w-20 bg-muted rounded mb-2" />
              <div className="h-7 w-16 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  const cards = [
    {
      title: t('descriptions'),
      value: stats.withDescription,
      total: stats.totalServices,
      icon: FileText,
      detail: `${stats.descManual} ${t('manual')} · ${stats.descAiApproved} ${t('aiApproved')}`,
      color: 'text-blue-600',
      pct: stats.withDescriptionPct,
    },
    {
      title: t('pendingReview'),
      value: stats.descAiDraft,
      icon: Clock,
      detail: stats.descAiDraft > 0 ? t('requiresApproval') : t('noPendingDrafts'),
      color: stats.descAiDraft > 0 ? 'text-amber-600' : 'text-emerald-600',
      badge: stats.descAiDraft > 0 ? 'amber' : undefined,
    },
    {
      title: t('translations'),
      value: stats.withTranslationsFr + stats.withTranslationsEn,
      icon: Languages,
      detail: `FR: ${stats.withTranslationsFr} · EN: ${stats.withTranslationsEn}`,
      color: 'text-violet-600',
    },
    {
      title: t('queue'),
      value: stats.queuePending + stats.queueProcessing,
      icon: RefreshCw,
      detail: `${stats.queueCompleted} ${t('ok')} · ${stats.queueFailed} err`,
      color: stats.queueFailed > 0 ? 'text-red-600' : 'text-emerald-600',
      badge: stats.queueFailed > 0 ? 'red' : undefined,
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((c) => {
        const Icon = c.icon
        return (
          <Card key={c.title} className="relative overflow-hidden">
            <CardContent className="pt-4 pb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {c.title}
                </span>
                <Icon className={`h-4 w-4 ${c.color}`} />
              </div>
              <div className="flex items-baseline gap-1.5">
                <span className="text-2xl font-bold tabular-nums">{c.value}</span>
                {c.total !== undefined && (
                  <span className="text-sm text-muted-foreground">/ {c.total}</span>
                )}
                {c.badge === 'amber' && (
                  <Badge variant="outline" className="ml-auto text-amber-700 border-amber-300 bg-amber-50 text-[10px]">
                    {t('pendingBadge')}
                  </Badge>
                )}
                {c.badge === 'red' && (
                  <Badge variant="destructive" className="ml-auto text-[10px]">
                    {t('errors')}
                  </Badge>
                )}
              </div>
              {c.pct !== undefined && (
                <div className="mt-1.5 h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all"
                    style={{ width: `${Math.min(c.pct, 100)}%` }}
                  />
                </div>
              )}
              <p className="text-[11px] text-muted-foreground mt-1">{c.detail}</p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

// ============================================================
// Approval Table
// ============================================================
function ApprovalTable({
  drafts,
  loading,
  onReview,
  t,
}: {
  drafts: PendingDraft[]
  loading: boolean
  onReview: (id: number, action: 'approve' | 'reject', editedText?: string) => Promise<void>
  t: (key: string) => string
}) {
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editText, setEditText] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const handleAction = async (id: number, action: 'approve' | 'reject') => {
    setActionLoading(`${id}-${action}`)
    try {
      const text = editingId === id && editText.trim() ? editText.trim() : undefined
      await onReview(id, action, text)
      setEditingId(null)
      setEditText('')
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!drafts.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
        <CheckCircle className="h-10 w-10 mb-2 text-emerald-500" />
        <p className="font-medium">{t('noPendingDrafts')}</p>
        <p className="text-sm">{t('allReviewed')}</p>
      </div>
    )
  }

  return (
    <div className="divide-y max-h-[480px] overflow-y-auto">
      {drafts.map((d) => (
        <div key={d.id} className="py-3 px-1 hover:bg-muted/30 transition-colors">
          <div className="flex items-start gap-3">
            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                {d.serviceCode && (
                  <Badge variant="outline" className="text-[10px] font-mono shrink-0">
                    {d.serviceCode}
                  </Badge>
                )}
                <span className="font-medium text-sm truncate">{d.nameEs}</span>
              </div>
              {d.ministryName && (
                <p className="text-[11px] text-muted-foreground truncate mb-1">
                  {d.ministryName}
                </p>
              )}

              {/* Description preview or edit */}
              {editingId === d.id ? (
                <Textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  className="text-sm mt-1 h-20"
                  maxLength={500}
                  placeholder={t('editPlaceholder')}
                />
              ) : (
                <p className="text-sm text-foreground/80 line-clamp-2 bg-amber-50 rounded px-2 py-1 border border-amber-200">
                  {d.descriptionEs || t('empty')}
                </p>
              )}
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-1 shrink-0">
              <Button
                size="sm"
                variant="default"
                className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700"
                onClick={() => handleAction(d.id, 'approve')}
                disabled={actionLoading !== null}
              >
                {actionLoading === `${d.id}-approve` ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <CheckCircle className="h-3 w-3 mr-1" />
                )}
                {t('approve')}
              </Button>

              {/* Reject with confirmation dialog */}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs text-red-600 hover:bg-red-50"
                    disabled={actionLoading !== null}
                  >
                    {actionLoading === `${d.id}-reject` ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <XCircle className="h-3 w-3 mr-1" />
                    )}
                    {t('reject')}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>{t('rejectConfirmTitle')}</AlertDialogTitle>
                    <AlertDialogDescription>{t('rejectConfirmDesc')}</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleAction(d.id, 'reject')}
                      className="bg-red-600 hover:bg-red-700"
                    >
                      {t('reject')}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              {editingId !== d.id ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => { setEditingId(d.id); setEditText(d.descriptionEs || '') }}
                >
                  <Pencil className="h-3 w-3 mr-1" />
                  {t('edit')}
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => { setEditingId(null); setEditText('') }}
                >
                  {t('cancel')}
                </Button>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ============================================================
// Queue Monitor Table
// ============================================================
function QueueTable({
  tasks,
  loading,
  onRetry,
  t,
}: {
  tasks: EnrichmentTask[]
  loading: boolean
  onRetry: (taskId: string) => Promise<void>
  t: (key: string) => string
}) {
  const [retrying, setRetrying] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!tasks.length) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Search className="h-8 w-8 mx-auto mb-2" />
        <p>{t('noTasks')}</p>
      </div>
    )
  }

  const statusBadge = (s: string) => {
    switch (s) {
      case 'completed': return <Badge className="bg-emerald-100 text-emerald-800 text-[10px]">{t('ok')}</Badge>
      case 'failed': return <Badge variant="destructive" className="text-[10px]">{t('error')}</Badge>
      case 'pending': return <Badge variant="secondary" className="text-[10px]">{t('pendingBadge')}</Badge>
      case 'processing': return <Badge className="bg-blue-100 text-blue-800 text-[10px]">{t('inProgress')}</Badge>
      default: return <Badge variant="outline" className="text-[10px]">{s}</Badge>
    }
  }

  const taskLabel = (taskType: string) => {
    switch (taskType) {
      case 'generate_description': return t('taskDescription')
      case 'translate_fr': return t('taskTranslateFr')
      case 'translate_en': return t('taskTranslateEn')
      case 'generate_keywords': return t('taskKeywords')
      case 'generate_ministry_description': return t('taskMinistryDesc')
      default: return taskType
    }
  }

  return (
    <div className="divide-y max-h-[400px] overflow-y-auto">
      <div className="grid grid-cols-[1fr_100px_70px_60px_70px] gap-2 px-2 py-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wide bg-muted/50 sticky top-0">
        <span>{t('service')}</span>
        <span>{t('type')}</span>
        <span>{t('status')}</span>
        <span>{t('tokens')}</span>
        <span>{t('action')}</span>
      </div>
      {tasks.map((task) => (
        <div key={task.id} className="grid grid-cols-[1fr_100px_70px_60px_70px] gap-2 px-2 py-2 items-start text-sm hover:bg-muted/30">
          <div className="min-w-0">
            <span className="font-medium truncate block">{task.nameEs || task.ministryName || `ID ${task.fiscalServiceId}`}</span>
            {task.serviceCode && (
              <span className="text-[10px] text-muted-foreground ml-1">[{task.serviceCode}]</span>
            )}
            {task.status === 'failed' && task.errorMessage && (
              <p className="text-[10px] text-red-500 truncate" title={task.errorMessage}>{task.errorMessage}</p>
            )}
            {task.status === 'completed' && task.outputData && (
              <p className="text-[11px] text-emerald-700 bg-emerald-50 rounded px-1.5 py-0.5 mt-1 line-clamp-2 border border-emerald-200">
                {(() => {
                  const od = task.outputData as Record<string, unknown>
                  return (od.descriptionEs || od.description || od.translatedText || JSON.stringify(od).slice(0, 150)) as string
                })()}
              </p>
            )}
          </div>
          <span className="text-xs">{taskLabel(task.taskType)}</span>
          {statusBadge(task.status)}
          <span className="text-xs tabular-nums text-muted-foreground">{task.tokensUsed || '-'}</span>
          <div>
            {task.status === 'failed' && (
              <Button
                size="sm"
                variant="ghost"
                className="h-6 text-[11px] px-2"
                onClick={async () => {
                  setRetrying(task.id)
                  try {
                    await onRetry(task.id)
                  } finally {
                    setRetrying(null)
                  }
                }}
                disabled={retrying !== null}
              >
                {retrying === task.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <RotateCcw className="h-3 w-3" />
                )}
              </Button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// ============================================================
// Main Page
// ============================================================
export default function EnrichmentAdminPage() {
  const t = useTranslations('enrichment')
  const { toast } = useToast()

  const [stats, setStats] = useState<EnrichmentStats | null>(null)
  const [drafts, setDrafts] = useState<PendingDraft[]>([])
  const [ministryDrafts, setMinistryDrafts] = useState<PendingDraft[]>([])
  const [recentTasks, setRecentTasks] = useState<EnrichmentTask[]>([])
  const [loading, setLoading] = useState(true)
  const [seedingServices, setSeedingServices] = useState(false)
  const [seedingMinistries, setSeedingMinistries] = useState(false)
  const [activeTab, setActiveTab] = useState('approval')
  const [queueFilter, setQueueFilter] = useState<'all' | 'completed' | 'failed' | 'pending'>('all')
  // Bulk visibility state
  const [ministries, setMinistries] = useState<MinistryOption[]>([])
  const [bulkMinistry, setBulkMinistry] = useState<string>('all')
  const [bulkSource, setBulkSource] = useState<string>('all')
  const [bulkLoading, setBulkLoading] = useState(false)
  // Processing state
  const [processing, setProcessing] = useState(false)
  const [showProgress, setShowProgress] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [s, d, md, r, m] = await Promise.all([
        enrichmentApi.getStats(),
        enrichmentApi.getPendingDrafts(),
        enrichmentApi.getPendingMinistryDrafts(),
        enrichmentApi.getRecent(30, queueFilter),
        enrichmentApi.getMinistries(),
      ])
      setStats(s)
      setDrafts(d)
      setMinistryDrafts(md)
      setRecentTasks(r)
      setMinistries(m)
    } catch {
      toast({ title: t('error'), description: t('loadError'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast, t, queueFilter])

  useEffect(() => { loadAll() }, [loadAll])

  // Check if processing is already running on page load
  useEffect(() => {
    const checkProgress = async () => {
      try {
        const p = await enrichmentApi.getProgress()
        if (p.status === 'running' || p.status === 'circuit_breaker_pause') {
          setShowProgress(true)
        }
      } catch {
        // ignore
      }
    }
    checkProgress()
  }, [])

  const handleFilterChange = useCallback(async (filter: 'all' | 'completed' | 'failed' | 'pending') => {
    setQueueFilter(filter)
  }, [])

  const handleReviewService = async (id: number, action: 'approve' | 'reject', editedText?: string) => {
    try {
      await enrichmentApi.reviewService(id, action, editedText)
      toast({
        title: action === 'approve' ? t('approved') : t('rejected'),
        description: `${t('service')} #${id} — ${action === 'approve' ? t('visibleOnSite') : t('deleted')}`,
      })
      setDrafts(prev => prev.filter(d => d.id !== id))
      setStats(prev => {
        if (!prev) return null
        const newDraft = prev.descAiDraft - 1
        if (action === 'approve') {
          const newWithDesc = prev.withDescription + 1
          return {
            ...prev,
            descAiDraft: newDraft,
            descAiApproved: prev.descAiApproved + 1,
            withDescription: newWithDesc,
            withDescriptionPct: prev.totalServices > 0
              ? Math.round(newWithDesc / prev.totalServices * 1000) / 10
              : 0,
          }
        }
        return { ...prev, descAiDraft: newDraft }
      })
    } catch {
      toast({ title: t('error'), description: t('actionError'), variant: 'destructive' })
    }
  }

  const handleReviewMinistry = async (id: number, action: 'approve' | 'reject', editedText?: string) => {
    try {
      await enrichmentApi.reviewMinistry(id, action, editedText)
      toast({
        title: action === 'approve' ? t('ministryApproved') : t('rejected'),
      })
      setMinistryDrafts(prev => prev.filter(d => d.id !== id))
      setStats(prev => prev ? { ...prev, descAiDraft: prev.descAiDraft - 1 } : null)
    } catch {
      toast({ title: t('error'), description: t('actionError'), variant: 'destructive' })
    }
  }

  const handleProcessingComplete = useCallback(() => {
    setShowProgress(false)
    setProcessing(false)
    toast({
      title: t('processingComplete'),
      description: t('processingCompleteDesc', { processed: 0, failed: 0, tokens: 0 }),
    })
    loadAll()
  }, [loadAll, toast, t])

  const handleProcessNow = async () => {
    setProcessing(true)
    try {
      const result = await enrichmentApi.processNow()
      if (result.status === 'running' || result.status === 'already_running') {
        setShowProgress(true)
        setActiveTab('queue')
        toast({
          title: t('autoProcessingStarted'),
          description: t('autoProcessingDesc', { total: result.total }),
        })
      } else if (result.status === 'idle') {
        setProcessing(false)
        toast({ title: t('processingIdle') })
      }
    } catch (e: unknown) {
      setProcessing(false)
      const msg = e instanceof Error ? e.message : t('error')
      toast({
        title: t('error'),
        description: msg.includes('429') ? t('waitOneMinute') : msg,
        variant: 'destructive',
      })
    }
  }

  const handleRetry = async (taskId: string) => {
    try {
      await enrichmentApi.retryTask(taskId)
      toast({ title: t('taskRetried'), description: t('taskRetriedDesc') })
      setRecentTasks(prev => prev.map(task => task.id === taskId ? { ...task, status: 'pending' } : task))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('retryError')
      toast({ title: t('error'), description: msg, variant: 'destructive' })
    }
  }

  const handleSeedBatch = async () => {
    setSeedingServices(true)
    try {
      const result = await enrichmentApi.seedBatch()
      const total = result.enqueuedDescriptions + result.enqueuedTranslations + (result.enqueuedKeywords || 0)
      toast({
        title: result.autoProcessing ? t('autoProcessingStarted') : t('seedLaunched'),
        description: result.autoProcessing
          ? t('autoProcessingDesc', { total })
          : t('seedResult', { descriptions: result.enqueuedDescriptions, translations: result.enqueuedTranslations }),
      })
      if (result.autoProcessing) {
        setShowProgress(true)
        setActiveTab('queue')
      }
      await loadAll()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('error')
      toast({
        title: t('error'),
        description: msg.includes('429') ? t('waitOneMinute') : msg,
        variant: 'destructive',
      })
    } finally {
      setSeedingServices(false)
    }
  }

  const handleSeedMinistries = async () => {
    setSeedingMinistries(true)
    try {
      const result = await enrichmentApi.seedMinistries()
      toast({
        title: result.autoProcessing ? t('autoProcessingStarted') : t('ministriesQueued'),
        description: result.autoProcessing
          ? t('autoProcessingDesc', { total: result.enqueuedMinistryDescriptions })
          : t('ministriesQueuedResult', { count: result.enqueuedMinistryDescriptions }),
      })
      if (result.autoProcessing) {
        setShowProgress(true)
        setActiveTab('queue')
      }
      await loadAll()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('error')
      toast({
        title: t('error'),
        description: msg.includes('429') ? t('waitOneMinute') : msg,
        variant: 'destructive',
      })
    } finally {
      setSeedingMinistries(false)
    }
  }

  const handleApproveAll = async () => {
    try {
      const result = await enrichmentApi.approveAll()
      toast({
        title: t('bulkApproveComplete'),
        description: t('bulkApproveResult', {
          services: result.approvedServices,
          ministries: result.approvedMinistries,
        }),
      })
      await loadAll()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('error')
      toast({
        title: t('error'),
        description: msg.includes('429') ? t('waitOneMinute') : msg,
        variant: 'destructive',
      })
    }
  }

  const handleBulkVisibility = async (visible: boolean) => {
    setBulkLoading(true)
    try {
      const source = bulkSource !== 'all' ? bulkSource : undefined
      const ministry = bulkMinistry !== 'all' ? Number(bulkMinistry) : undefined
      const result = await enrichmentApi.bulkVisibility(visible, source, ministry)
      toast({
        title: visible ? t('bulkShowComplete') : t('bulkHideComplete'),
        description: t('bulkVisibilityResult', { count: result.affected }),
      })
      await loadAll()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('error')
      toast({
        title: t('error'),
        description: msg.includes('429') ? t('waitOneMinute') : msg,
        variant: 'destructive',
      })
    } finally {
      setBulkLoading(false)
    }
  }

  const pendingCount = drafts.length + ministryDrafts.length
  const missingDescCount = (stats?.totalServices ?? 0) - (stats?.withDescription ?? 0)

  return (
    <div className="space-y-4 p-4 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h1 className="text-xl font-bold">{t('title')}</h1>
          {pendingCount > 0 && (
            <Badge variant="outline" className="text-amber-700 border-amber-300 bg-amber-50">
              {pendingCount} {t('pending')}
            </Badge>
          )}
        </div>
        <Button variant="ghost" size="sm" onClick={loadAll} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Processing Progress Bar (visible when agent is running) */}
      {showProgress && (
        <ProcessingProgress onComplete={handleProcessingComplete} t={t} />
      )}

      {/* Stats */}
      <StatsCards stats={stats} loading={loading} t={t} />

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-4 w-full">
          <TabsTrigger value="approval" className="text-xs sm:text-sm">
            <CheckCircle className="h-3.5 w-3.5 mr-1 hidden sm:inline" />
            {t('tabApproval')}
            {drafts.length > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">{drafts.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="ministries" className="text-xs sm:text-sm">
            <Building2 className="h-3.5 w-3.5 mr-1 hidden sm:inline" />
            {t('tabMinistries')}
            {ministryDrafts.length > 0 && (
              <Badge variant="secondary" className="ml-1.5 text-[10px] px-1.5">{ministryDrafts.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="queue" className="text-xs sm:text-sm">
            <RefreshCw className="h-3.5 w-3.5 mr-1 hidden sm:inline" />
            {t('tabQueue')}
          </TabsTrigger>
          <TabsTrigger value="actions" className="text-xs sm:text-sm">
            <Sparkles className="h-3.5 w-3.5 mr-1 hidden sm:inline" />
            {t('tabActions')}
          </TabsTrigger>
        </TabsList>

        {/* Tab: Service Approval */}
        <TabsContent value="approval">
          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base">{t('serviceDescriptions')}</CardTitle>
              {drafts.length > 0 && (
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button size="sm" variant="outline" className="text-xs">
                      <CheckCheck className="h-3.5 w-3.5 mr-1" />
                      {t('approveAll')} ({drafts.length})
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('approveAllTitle')}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('approveAllDesc', { services: drafts.length, ministries: ministryDrafts.length })}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                      <AlertDialogAction onClick={handleApproveAll} className="bg-emerald-600 hover:bg-emerald-700">
                        {t('approveAll')}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </CardHeader>
            <CardContent className="pt-0">
              <ApprovalTable
                drafts={drafts}
                loading={loading}
                onReview={handleReviewService}
                t={t}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Ministry Approval */}
        <TabsContent value="ministries">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{t('ministryDescriptions')}</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ApprovalTable
                drafts={ministryDrafts}
                loading={loading}
                onReview={handleReviewMinistry}
                t={t}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Queue Monitor + Process Now button */}
        <TabsContent value="queue">
          <Card>
            <CardHeader className="pb-2 flex flex-row items-center justify-between">
              <CardTitle className="text-base">{t('queueMonitor')}</CardTitle>
              <div className="flex items-center gap-2">
                {/* Process Now button (Option A) */}
                <Button
                  size="sm"
                  variant="default"
                  className="h-7 text-xs bg-blue-600 hover:bg-blue-700"
                  onClick={handleProcessNow}
                  disabled={processing || showProgress}
                >
                  {processing ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                  ) : (
                    <Play className="h-3 w-3 mr-1" />
                  )}
                  {t('processNow')}
                </Button>

                {/* Status filter buttons */}
                <div className="flex gap-1">
                  {(['all', 'completed', 'failed', 'pending'] as const).map((f) => (
                    <Button
                      key={f}
                      size="sm"
                      variant={queueFilter === f ? 'default' : 'ghost'}
                      className="h-6 text-[11px] px-2"
                      onClick={() => handleFilterChange(f)}
                    >
                      {t(`filter${f.charAt(0).toUpperCase() + f.slice(1)}` as 'filterAll' | 'filterCompleted' | 'filterFailed' | 'filterPending')}
                    </Button>
                  ))}
                </div>
                {stats && (
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="flex items-center gap-0.5">
                      <Clock className="h-3 w-3" /> {stats.queuePending} {t('queuePending')}
                    </span>
                    <ChevronRight className="h-3 w-3" />
                    <span className="flex items-center gap-0.5">
                      <CheckCircle className="h-3 w-3 text-emerald-500" /> {stats.queueCompleted}
                    </span>
                    <ChevronRight className="h-3 w-3" />
                    <span className="flex items-center gap-0.5">
                      <AlertTriangle className="h-3 w-3 text-red-500" /> {stats.queueFailed}
                    </span>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <QueueTable tasks={recentTasks} loading={loading} onRetry={handleRetry} t={t} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab: Actions */}
        <TabsContent value="actions">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-blue-600" />
                  {t('generateDescriptions')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  {t('generateDescriptionsDesc')}
                </p>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button disabled={seedingServices || showProgress} className="w-full">
                      {seedingServices ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Sparkles className="h-4 w-4 mr-2" />}
                      {t('generateServices')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('seedConfirmTitle')}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('seedConfirmDescAuto', { count: missingDescCount })}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                      <AlertDialogAction onClick={handleSeedBatch}>{t('confirm')}</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-violet-600" />
                  {t('generateMinistriesTitle')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  {t('generateMinistriesDesc')}
                </p>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" disabled={seedingMinistries || showProgress} className="w-full">
                      {seedingMinistries ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Building2 className="h-4 w-4 mr-2" />}
                      {t('generateMinistries')}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>{t('seedMinistryConfirmTitle')}</AlertDialogTitle>
                      <AlertDialogDescription>
                        {t('seedMinistryConfirmDesc')}
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                      <AlertDialogAction onClick={handleSeedMinistries}>{t('confirm')}</AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </CardContent>
            </Card>

            {/* Bulk visibility toggle */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Eye className="h-4 w-4 text-emerald-600" />
                  {t('bulkVisibilityTitle')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  {t('bulkVisibilityDesc')}
                </p>

                {/* Filters */}
                <div className="flex flex-wrap items-end gap-3 mb-4">
                  <div className="flex-1 min-w-[200px]">
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">
                      {t('filterMinistry')}
                    </label>
                    <Select value={bulkMinistry} onValueChange={setBulkMinistry}>
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">{t('allMinistries')}</SelectItem>
                        {ministries.map((m) => (
                          <SelectItem key={m.id} value={String(m.id)}>
                            {m.nameEs} ({m.serviceCount})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="w-[200px]">
                    <label className="text-xs font-medium text-muted-foreground mb-1 block">
                      {t('filterSource')}
                    </label>
                    <Select value={bulkSource} onValueChange={setBulkSource}>
                      <SelectTrigger className="h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">{t('allSources')}</SelectItem>
                        <SelectItem value="manual">{t('manual')}</SelectItem>
                        <SelectItem value="ai_draft">{t('aiDraft')}</SelectItem>
                        <SelectItem value="ai_approved">{t('aiApproved')}</SelectItem>
                        <SelectItem value="ai_generated">{t('aiGenerated')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex gap-3">
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="default" disabled={bulkLoading} className="flex-1 bg-emerald-600 hover:bg-emerald-700">
                        {bulkLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Eye className="h-4 w-4 mr-2" />}
                        {t('bulkShow')}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('bulkShowConfirmTitle')}</AlertDialogTitle>
                        <AlertDialogDescription>{t('bulkShowConfirmDesc')}</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleBulkVisibility(true)} className="bg-emerald-600 hover:bg-emerald-700">
                          {t('confirm')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" disabled={bulkLoading} className="flex-1 text-red-600 hover:bg-red-50">
                        {bulkLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <EyeOff className="h-4 w-4 mr-2" />}
                        {t('bulkHide')}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('bulkHideConfirmTitle')}</AlertDialogTitle>
                        <AlertDialogDescription>{t('bulkHideConfirmDesc')}</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleBulkVisibility(false)} className="bg-red-600 hover:bg-red-700">
                          {t('confirm')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
