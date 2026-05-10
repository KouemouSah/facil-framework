'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import {
  FileStack,
  ArrowLeft,
  Loader2,
  Users,
  CreditCard,
  FileCheck,
  CheckCircle,
  AlertCircle,
  ExternalLink,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { batchApi } from '../services/batch-api'
import type { BatchDetail as BatchDetailType } from '../types'
import {
  getBatchStatusColor,
  getBatchStatusKey,
  getItemStatusColor,
  getBatchItemStatusKey,
} from '../types'

interface BatchDetailProps {
  batchId: string
}

export function BatchDetail({ batchId }: BatchDetailProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('batch')

  const [isLoading, setIsLoading] = useState(true)
  const [batch, setBatch] = useState<BatchDetailType | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      setIsLoading(true)
      try {
        const result = await batchApi.getBatch(batchId)
        setBatch(result)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setIsLoading(false)
      }
    }
    load()
  }, [batchId])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    )
  }

  if (error || !batch) {
    return (
      <div className="text-center py-16">
        <AlertCircle className="h-10 w-10 mx-auto text-red-400 mb-3" />
        <p className="text-gray-500">{error || t('detail.notFound')}</p>
        <Button
          variant="outline"
          className="mt-4"
          onClick={() => router.push(`/${locale}/dashboard/batch-requests`)}
        >
          {t('detail.backToList')}
        </Button>
      </div>
    )
  }

  const formatAmount = (amount: number | null) =>
    amount !== null
      ? new Intl.NumberFormat(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-GQ', {
          style: 'currency',
          currency: batch.currency,
          minimumFractionDigits: 0,
        }).format(amount)
      : '\u2014'

  const items = batch.items || []

  return (
    <div className="space-y-6">
      {/* F-024: Breadcrumb navigation */}
      <nav className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <button
          className="hover:text-foreground transition-colors"
          onClick={() => router.push(`/${locale}/dashboard`)}
        >
          Dashboard
        </button>
        <span>/</span>
        <button
          className="hover:text-foreground transition-colors"
          onClick={() => router.push(`/${locale}/dashboard/batch-requests`)}
        >
          {t('title')}
        </button>
        <span>/</span>
        <span className="text-foreground font-medium font-mono">
          {batch.reference || batchId.slice(0, 8)}
        </span>
      </nav>

      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push(`/${locale}/dashboard/batch-requests`)}
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <FileStack className="h-6 w-6 text-blue-600" />
            <h1 className="text-2xl font-bold">
              {batch.reference || t('detail.batch')}
            </h1>
            <Badge className={getBatchStatusColor(batch.status)}>
              {t(getBatchStatusKey(batch.status))}
            </Badge>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            {batch.workflowCode} {'\u2014'} {batch.solicitudType} {'\u2014'} {t('detail.createdOn')}{' '}
            {new Date(batch.createdAt).toLocaleDateString(locale)}
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-1">
              <Users className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-gray-500">{t('beneficiaries')}</span>
            </div>
            <p className="text-2xl font-bold">{batch.totalItems}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-xs text-gray-500">{t('detail.ready')}</span>
            </div>
            <p className="text-2xl font-bold text-green-600">
              {batch.itemsReady}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-1">
              <FileCheck className="h-4 w-4 text-purple-500" />
              <span className="text-xs text-gray-500">{t('detail.submitted')}</span>
            </div>
            <p className="text-2xl font-bold text-purple-600">
              {batch.itemsSubmitted}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3">
            <div className="flex items-center gap-2 mb-1">
              <CreditCard className="h-4 w-4 text-amber-500" />
              <span className="text-xs text-gray-500">{t('detail.total')}</span>
            </div>
            <p className="text-2xl font-bold">
              {formatAmount(batch.totalAmount)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      {batch.notes && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t('detail.notes')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600">{batch.notes}</p>
          </CardContent>
        </Card>
      )}

      {/* Shared documents */}
      {batch.sharedDocuments.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">
              {t('sharedDocs.title')} ({batch.sharedDocuments.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {batch.sharedDocuments.map((doc) => (
                <div
                  key={doc.documentCode}
                  className="flex items-center gap-2 text-sm"
                >
                  <FileCheck className="h-4 w-4 text-green-500" />
                  <span className="font-medium">{doc.documentCode}</span>
                  <span className="text-gray-400">{'\u2014'} {doc.fileName}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Beneficiaries table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            {t('beneficiaries')} ({items.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10">#</TableHead>
                  <TableHead>{t('detail.name')}</TableHead>
                  <TableHead>{t('detail.identifier')}</TableHead>
                  <TableHead>{t('detail.documents')}</TableHead>
                  <TableHead>{t('amount')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead>{t('detail.request')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item, idx) => (
                  <TableRow key={item.id}>
                    <TableCell className="text-gray-400">
                      {idx + 1}
                    </TableCell>
                    <TableCell className="font-medium">
                      {item.beneficiaryName}
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.beneficiaryIdentifier ? (
                        <span>
                          <span className="text-gray-400 uppercase text-xs">
                            {item.beneficiaryIdentifierType}:{' '}
                          </span>
                          {item.beneficiaryIdentifier}
                        </span>
                      ) : (
                        '\u2014'
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <span className="text-sm">
                          {item.assignedDocuments.length}
                        </span>
                        {item.missingDocuments.length > 0 && (
                          <Badge className="bg-red-100 text-red-700 text-[10px]">
                            {item.missingDocuments.length} {t('detail.missing')}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {item.itemAmount !== null
                        ? formatAmount(item.itemAmount)
                        : formatAmount(batch.perItemAmount)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={`${getItemStatusColor(item.status)} text-xs`}
                      >
                        {t(getBatchItemStatusKey(item.status))}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {item.serviceRequestId ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 text-xs"
                          onClick={() =>
                            router.push(
                              `/${locale}/dashboard/service-requests/${item.serviceRequestId}`
                            )
                          }
                        >
                          <ExternalLink className="h-3 w-3 mr-1" />
                          {t('detail.view')}
                        </Button>
                      ) : (
                        <span className="text-gray-300 text-xs">{'\u2014'}</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
