'use client'

/**
 * AgentBatchDetail - Batch detail with items, bulk actions, shared docs
 * @module agent-dashboard/components/batch
 */

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  FileStack,
  ArrowLeft,
  CheckCircle,
  XCircle,
  Users,
  DollarSign,
  Clock,
  Eye,
  Loader2,
  Mail,
  User,
  FileText,
} from 'lucide-react'
import Link from 'next/link'
import { toast } from 'sonner'
import {
  agentRequestsApi,
  type AgentBatchDetail as AgentBatchDetailType,
} from '../../services/agent-requests-api'

const SR_STATUS_COLORS: Record<string, string> = {
  submitted: 'bg-cyan-100 text-cyan-800',
  SUBMITTED: 'bg-cyan-100 text-cyan-800',
  pending_review: 'bg-teal-100 text-teal-800',
  PENDING_REVIEW: 'bg-teal-100 text-teal-800',
  UNDER_REVIEW: 'bg-teal-100 text-teal-800',
  DOSSIER_VALIDE: 'bg-indigo-100 text-indigo-800',
  APPROVED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  COMPLETED: 'bg-green-200 text-green-900',
  EXPIRED: 'bg-gray-200 text-gray-600',
}

const REJECTION_REASONS = [
  'documents_incomplete',
  'documents_invalid',
  'identity_mismatch',
  'payment_issue',
  'other',
]

interface AgentBatchDetailProps {
  entityCode: string
  batchId: string
  basePath: string
}

export function AgentBatchDetail({ entityCode, batchId, basePath }: AgentBatchDetailProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('agent')
  const tBatch = useTranslations('batch')

  const [batch, setBatch] = useState<AgentBatchDetailType | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [bulkDialog, setBulkDialog] = useState<'approve' | 'reject' | null>(null)
  const [bulkComments, setBulkComments] = useState('')
  const [rejectionReason, setRejectionReason] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)

  const fetchDetail = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await agentRequestsApi.getEntityBatchDetail(entityCode, batchId)
      setBatch(result)
    } catch {
      toast.error(t('batch.loadError', { defaultValue: 'Error al cargar el lote' }))
    } finally {
      setIsLoading(false)
    }
  }, [entityCode, batchId, t])

  useEffect(() => { fetchDetail() }, [fetchDetail])

  const pendingCount = batch?.items?.filter(
    (i) => i.sr_status && ['SUBMITTED', 'PENDING_REVIEW'].includes(i.sr_status)
  ).length ?? 0

  const completedCount = batch?.items?.filter(
    (i) => i.sr_status && ['DOSSIER_VALIDE', 'APPROVED', 'REJECTED', 'COMPLETED', 'EXPIRED'].includes(i.sr_status)
  ).length ?? 0

  const handleBulkDecision = async (decision: 'approve' | 'reject') => {
    if (!batch) return
    setIsProcessing(true)
    try {
      const result = await agentRequestsApi.bulkDecision(entityCode, batchId, {
        decision,
        comments: bulkComments || undefined,
        rejectionReason: decision === 'reject' ? rejectionReason : undefined,
      })
      toast.success(
        t('batch.bulkResult', { processed: result.processed, failed: result.failed })
      )
      if (result.batch_completed) {
        toast.info(t('batch.batchAutoCompleted'))
      }
      setBulkDialog(null)
      setBulkComments('')
      setRejectionReason('')
      fetchDetail()
    } catch {
      toast.error(t('batch.bulkError'))
    } finally {
      setIsProcessing(false)
    }
  }

  const formatAmount = (amount: number | null) => {
    if (amount == null || amount === 0) return '-'
    return new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount) + ' FCFA'
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!batch) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">{t('batch.noBatches')}</p>
        <Link href={`/${locale}${basePath}/batch-requests`}>
          <Button variant="outline" className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('batch.backToList')}
          </Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* F-024: Breadcrumb navigation */}
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Link href={`/${locale}${basePath}`} className="hover:text-foreground transition-colors">
          Dashboard
        </Link>
        <span>/</span>
        <Link href={`/${locale}${basePath}/batch-requests`} className="hover:text-foreground transition-colors">
          {t('batch.title')}
        </Link>
        <span>/</span>
        <span className="text-foreground font-medium font-mono">
          {batch.reference}
        </span>
      </nav>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href={`/${locale}${basePath}/batch-requests`}>
            <Button variant="ghost" size="sm">
              <ArrowLeft className="h-4 w-4 mr-1" />
            </Button>
          </Link>
          <FileStack className="h-6 w-6 text-indigo-600" />
          <div>
            <h1 className="text-2xl font-bold font-mono">{batch.reference}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <User className="h-3 w-3" />
              <span>{t('batch.submittedBy')}: {batch.submitted_by_name}</span>
              {batch.submitted_by_email && (
                <>
                  <Mail className="h-3 w-3 ml-2" />
                  <span>{batch.submitted_by_email}</span>
                </>
              )}
            </div>
          </div>
        </div>
        <Badge className={batch.status === 'COMPLETED' ? 'bg-green-200 text-green-900' : 'bg-indigo-100 text-indigo-700'}>
          {tBatch(`status.${batch.status}` as Parameters<typeof tBatch>[0])}
        </Badge>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Total</span>
            </div>
            <p className="text-2xl font-bold mt-1">{batch.total_items}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm text-muted-foreground">{t('batch.filterCompleted')}</span>
            </div>
            <p className="text-2xl font-bold mt-1">{completedCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-muted-foreground">{t('batch.colPending')}</span>
            </div>
            <p className="text-2xl font-bold mt-1">{pendingCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{t('batch.totalAmount')}</span>
            </div>
            <p className="text-xl font-bold mt-1">{formatAmount(batch.total_amount)}</p>
          </CardContent>
        </Card>
      </div>

      {/* Bulk actions */}
      {pendingCount > 0 && (
        <div className="flex gap-3">
          <Button
            onClick={() => setBulkDialog('approve')}
            className="bg-green-600 hover:bg-green-700"
          >
            <CheckCircle className="h-4 w-4 mr-2" />
            {t('batch.bulkApprove')} ({pendingCount})
          </Button>
          <Button
            variant="destructive"
            onClick={() => setBulkDialog('reject')}
          >
            <XCircle className="h-4 w-4 mr-2" />
            {t('batch.bulkReject')} ({pendingCount})
          </Button>
        </div>
      )}

      {/* Shared documents */}
      {batch.shared_documents && batch.shared_documents.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t('batch.sharedDocs')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {batch.shared_documents.map((doc) => (
                <Badge key={doc.document_code} variant="outline" title={doc.file_name}>
                  {doc.file_name || doc.document_code.replace(/_/g, ' ')}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Items table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t('batch.items')}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]">#</TableHead>
                <TableHead>{t('batch.colBeneficiary')}</TableHead>
                <TableHead>{t('batch.colIdentifier')}</TableHead>
                <TableHead>{t('batch.srReference')}</TableHead>
                <TableHead>{t('batch.srStatus')}</TableHead>
                <TableHead>{t('batch.colAgent')}</TableHead>
                <TableHead className="w-[80px]">{t('batch.colActions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(batch.items ?? []).map((item, idx) => (
                <TableRow key={item.id}>
                  <TableCell className="text-muted-foreground">{idx + 1}</TableCell>
                  <TableCell className="font-medium">{item.beneficiary_name}</TableCell>
                  <TableCell className="font-mono text-sm">
                    {item.beneficiary_identifier || '-'}
                  </TableCell>
                  <TableCell className="font-mono text-sm">
                    {item.sr_reference || '-'}
                  </TableCell>
                  <TableCell>
                    {item.sr_status ? (
                      <Badge className={SR_STATUS_COLORS[item.sr_status] || 'bg-gray-100'}>
                        {t(`batch.statuses.${item.sr_status}` as Parameters<typeof t>[0], { defaultValue: item.sr_status })}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">
                    {item.sr_assigned_to || '-'}
                  </TableCell>
                  <TableCell>
                    {item.service_request_id && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          const entitySlug = entityCode.toLowerCase().replace(/_/g, '-')
                          router.push(`/${locale}/dashboard/agent/${entitySlug}/request/${item.service_request_id}`)
                        }}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Bulk decision dialog */}
      <Dialog open={bulkDialog !== null} onOpenChange={() => setBulkDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {bulkDialog === 'approve' ? t('batch.bulkApprove') : t('batch.bulkReject')}
            </DialogTitle>
            <DialogDescription>
              {bulkDialog === 'approve'
                ? t('batch.confirmBulkApprove', { count: pendingCount })
                : t('batch.confirmBulkReject', { count: pendingCount })
              }
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {bulkDialog === 'reject' && (
              <div className="space-y-2">
                <Label>{t('batch.rejectionReason')}</Label>
                <Select value={rejectionReason} onValueChange={setRejectionReason}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('batch.rejectionReasonPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {REJECTION_REASONS.map((reason) => (
                      <SelectItem key={reason} value={reason}>
                        {t(`batch.rejectionReasons.${reason}` as Parameters<typeof t>[0], { defaultValue: reason.replace(/_/g, ' ') })}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-2">
              <Label>{t('batch.comments')}</Label>
              <Textarea
                value={bulkComments}
                onChange={(e) => setBulkComments(e.target.value)}
                placeholder={t('batch.commentsPlaceholder')}
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDialog(null)} disabled={isProcessing}>
              {t('batch.cancel')}
            </Button>
            <Button
              onClick={() => bulkDialog && handleBulkDecision(bulkDialog)}
              disabled={isProcessing || (bulkDialog === 'reject' && !rejectionReason)}
              className={bulkDialog === 'approve' ? 'bg-green-600 hover:bg-green-700' : ''}
              variant={bulkDialog === 'reject' ? 'destructive' : 'default'}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  {t('batch.bulkProcessing')}
                </>
              ) : bulkDialog === 'approve' ? (
                t('batch.confirm')
              ) : (
                t('batch.confirm')
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Notes */}
      {batch.notes && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('batch.colNotes')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{batch.notes}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
