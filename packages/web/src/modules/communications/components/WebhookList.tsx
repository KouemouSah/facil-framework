'use client'

/**
 * WebhookList Component
 * Displays list of webhook configurations with actions
 */

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import {
  MoreHorizontal,
  Plus,
  Power,
  PowerOff,
  Edit,
  Trash2,
  TestTube,
  FileText,
} from 'lucide-react'
import { format } from 'date-fns'
import {
  useWebhooks,
  useDeleteWebhook,
  useToggleWebhook,
} from '../hooks/useWebhooks'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import type { WebhookResponse } from '../types'

interface WebhookListProps {
  locale: string
}

export function WebhookList({ locale }: WebhookListProps) {
  const router = useRouter()
  const t = useTranslations('admin.webhooks')
  const [page, setPage] = useState(1)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  const { data, isLoading, error } = useWebhooks({ page, pageSize: 20 })
  const deleteMutation = useDeleteWebhook()
  const { toggle, isLoading: isToggling } = useToggleWebhook()

  const handleDelete = async () => {
    if (deleteId) {
      await deleteMutation.mutateAsync(deleteId)
      setDeleteId(null)
    }
  }

  const handleToggle = (id: number, currentStatus: boolean) => {
    toggle(id, currentStatus)
  }

  const getStatusBadge = (webhook: WebhookResponse) => {
    if (!webhook.isActive) {
      return <Badge variant="secondary">{t('statusInactive')}</Badge>
    }

    if (!webhook.lastTriggeredAt) {
      return <Badge variant="outline">{t('statusNeverTriggered')}</Badge>
    }

    if (webhook.lastStatus === 'success') {
      return <Badge variant="default">{t('statusActive')}</Badge>
    }

    return <Badge variant="destructive">{t('statusError')}</Badge>
  }

  const getTypeBadge = (type: string) => {
    const colors: Record<string, string> = {
      whatsapp: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
      custom: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    }

    return (
      <Badge className={colors[type] || ''} variant="outline">
        {type}
      </Badge>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-red-600">
            {t('errorLoading', { message: error.message })}
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">{t('title')}</h2>
          <p className="text-muted-foreground">
            {t('description')}
          </p>
        </div>
        <Link href={`/${locale}/dashboard/admin/communications/webhooks/new`}>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            {t('newWebhook')}
          </Button>
        </Link>
      </div>

      {data && (
        <div className="text-sm text-muted-foreground">
          {t('showingCount', { shown: data.webhooks.length, total: data.total })}
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('name')}</TableHead>
                <TableHead>{t('type')}</TableHead>
                <TableHead>{t('endpoint')}</TableHead>
                <TableHead>{t('status')}</TableHead>
                <TableHead>{t('lastTriggered')}</TableHead>
                <TableHead className="text-right">{t('actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Skeleton className="h-4 w-[200px]" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-6 w-[80px]" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-[300px]" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-6 w-[80px]" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-4 w-[150px]" />
                    </TableCell>
                    <TableCell>
                      <Skeleton className="h-8 w-8 rounded-md" />
                    </TableCell>
                  </TableRow>
                ))
              ) : data?.webhooks.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="h-24 text-center">
                    {t('noWebhooks')}
                  </TableCell>
                </TableRow>
              ) : (
                data?.webhooks.map((webhook) => (
                  <TableRow key={webhook.id}>
                    <TableCell className="font-medium">{webhook.name}</TableCell>
                    <TableCell>{getTypeBadge(webhook.webhookType)}</TableCell>
                    <TableCell className="max-w-md truncate font-mono text-sm">
                      {webhook.endpointUrl}
                    </TableCell>
                    <TableCell>{getStatusBadge(webhook)}</TableCell>
                    <TableCell>
                      {webhook.lastTriggeredAt
                        ? format(new Date(webhook.lastTriggeredAt), 'MMM d, yyyy HH:mm')
                        : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreHorizontal className="h-4 w-4" />
                            <span className="sr-only">Open menu</span>
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onClick={() =>
                              router.push(
                                `/${locale}/dashboard/admin/communications/webhooks/${webhook.id}/edit`
                              )
                            }
                          >
                            <Edit className="mr-2 h-4 w-4" />
                            {t('edit')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              router.push(
                                `/${locale}/dashboard/admin/communications/webhooks/${webhook.id}/test`
                              )
                            }
                          >
                            <TestTube className="mr-2 h-4 w-4" />
                            {t('testWebhook')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() =>
                              router.push(
                                `/${locale}/dashboard/admin/communications/webhooks/${webhook.id}/logs`
                              )
                            }
                          >
                            <FileText className="mr-2 h-4 w-4" />
                            {t('viewLogs')}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => handleToggle(webhook.id, webhook.isActive)}
                            disabled={isToggling}
                          >
                            {webhook.isActive ? (
                              <>
                                <PowerOff className="mr-2 h-4 w-4" />
                                {t('disable')}
                              </>
                            ) : (
                              <>
                                <Power className="mr-2 h-4 w-4" />
                                {t('enable')}
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => setDeleteId(webhook.id)}
                            className="text-red-600"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            {t('delete')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {data && data.totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            {t('previous')}
          </Button>
          <span className="text-sm text-muted-foreground">
            {t('pageOf', { current: page, total: data.totalPages })}
          </span>
          <Button
            variant="outline"
            onClick={() => setPage((p) => Math.min(data.totalPages, p + 1))}
            disabled={page === data.totalPages}
          >
            {t('next')}
          </Button>
        </div>
      )}

      <AlertDialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              {t('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
