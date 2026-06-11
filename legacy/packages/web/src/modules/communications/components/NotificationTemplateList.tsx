/**
 * NotificationTemplateList Component
 * Displays a list of notification templates with filtering and actions
 */

'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { Plus, Search, Edit, Trash2, Eye, Filter, CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useNotificationTemplates, useDeleteNotificationTemplate } from '../hooks/useNotificationTemplates'
import type { NotificationType } from '../types/notification-template'
import { NOTIFICATION_TYPE_LABELS, NOTIFICATION_PRIORITY_LABELS } from '../types/notification-template'

interface NotificationTemplateListProps {
  locale: string
}

export function NotificationTemplateList(_props: NotificationTemplateListProps) {
  const { locale } = _props
  const tCommon = useTranslations('common')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [notificationType, setNotificationType] = useState<NotificationType | 'all'>('all')
  const [isActive, setIsActive] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  const { data, isLoading, error } = useNotificationTemplates({
    page,
    pageSize,
    search: search || undefined,
    notificationType: notificationType !== 'all' ? notificationType : undefined,
    isActive,
  })

  const handlePageSizeChange = (newSize: string) => {
    setPageSize(Number(newSize))
    setPage(1) // Reset to first page when changing page size
  }

  const deleteMutation = useDeleteNotificationTemplate()

  const handleDelete = async () => {
    if (deleteId) {
      await deleteMutation.mutateAsync(deleteId)
      setDeleteId(null)
    }
  }

  const getNotificationTypeBadge = (type: NotificationType) => {
    const colors = {
      info: 'bg-blue-100 text-blue-800 border-blue-200',
      success: 'bg-green-100 text-green-800 border-green-200',
      warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      error: 'bg-red-100 text-red-800 border-red-200',
    }

    return (
      <Badge variant="outline" className={colors[type]}>
        {NOTIFICATION_TYPE_LABELS[type]}
      </Badge>
    )
  }

  const getPriorityBadge = (priority: string) => {
    const colors = {
      low: 'bg-gray-100 text-gray-800 border-gray-200',
      normal: 'bg-blue-100 text-blue-800 border-blue-200',
      high: 'bg-orange-100 text-orange-800 border-orange-200',
      urgent: 'bg-red-100 text-red-800 border-red-200',
    }

    return (
      <Badge variant="outline" className={colors[priority as keyof typeof colors]}>
        {NOTIFICATION_PRIORITY_LABELS[priority as keyof typeof NOTIFICATION_PRIORITY_LABELS]}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Notification Templates</h1>
          <p className="text-muted-foreground">
            Manage notification templates for in-app notifications
          </p>
        </div>
        <Link href={`/${locale}/dashboard/admin/communications/notification-templates/new`}>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Template
          </Button>
        </Link>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
          <CardDescription>Filter notification templates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search templates..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Type</label>
              <Select
                value={notificationType}
                onValueChange={(value) => setNotificationType(value as NotificationType | 'all')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="info">Info</SelectItem>
                  <SelectItem value="success">Success</SelectItem>
                  <SelectItem value="warning">Warning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">{tCommon('status')}</label>
              <Select
                value={isActive === undefined ? 'all' : isActive ? 'active' : 'inactive'}
                onValueChange={(value) =>
                  setIsActive(value === 'all' ? undefined : value === 'active')
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{tCommon('all')}</SelectItem>
                  <SelectItem value="active">{tCommon('active')}</SelectItem>
                  <SelectItem value="inactive">{tCommon('inactive')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setSearch('')
                  setNotificationType('all')
                  setIsActive(undefined)
                }}
                className="w-full"
              >
                {tCommon('clearFilters') || 'Clear Filters'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Templates List */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto mb-4" />
                <p className="text-muted-foreground">Loading templates...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
                <p className="text-destructive">Failed to load templates</p>
                <p className="text-sm text-muted-foreground">{error.message}</p>
              </div>
            </div>
          ) : !data?.templates || data.templates.length === 0 ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <p className="text-muted-foreground">No templates found</p>
                <Link href={`/${locale}/dashboard/admin/communications/notification-templates/new`}>
                  <Button variant="link" className="mt-2">
                    Create your first template
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Template Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Variables</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.templates.map((template) => (
                    <TableRow key={template.id}>
                      <TableCell className="font-mono text-sm">{template.templateCode}</TableCell>
                      <TableCell>
                        <div>
                          <div className="font-medium">{template.nameEs}</div>
                          {template.titleEs && (
                            <div className="text-sm text-muted-foreground">{template.titleEs}</div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{getNotificationTypeBadge(template.notificationType)}</TableCell>
                      <TableCell>{getPriorityBadge(template.priority)}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{template.variables.length}</Badge>
                      </TableCell>
                      <TableCell>
                        {template.isActive ? (
                          <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                            <CheckCircle className="mr-1 h-3 w-3" />
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-200">
                            <XCircle className="mr-1 h-3 w-3" />
                            Inactive
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Link
                            href={`/${locale}/dashboard/admin/communications/notification-templates/${template.id}`}
                          >
                            <Button variant="ghost" size="sm">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Link
                            href={`/${locale}/dashboard/admin/communications/notification-templates/${template.id}/edit`}
                          >
                            <Button variant="ghost" size="sm">
                              <Edit className="h-4 w-4" />
                            </Button>
                          </Link>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteId(template.id)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              {data && (
                <div className="flex items-center justify-between border-t p-4">
                  <div className="flex items-center gap-4">
                    <div className="text-sm text-muted-foreground">
                      Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, data.total)} of {data.total}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">Rows:</span>
                      <Select value={String(pageSize)} onValueChange={handlePageSizeChange}>
                        <SelectTrigger className="w-[70px] h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="10">10</SelectItem>
                          <SelectItem value="20">20</SelectItem>
                          <SelectItem value="50">50</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  {data.totalPages > 1 && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage(1)}
                        disabled={page === 1}
                      >
                        {'<<'}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                      >
                        Previous
                      </Button>
                      {/* Page Numbers */}
                      {Array.from({ length: Math.min(5, data.totalPages) }, (_, i) => {
                        let pageNum: number
                        if (data.totalPages <= 5) {
                          pageNum = i + 1
                        } else if (page <= 3) {
                          pageNum = i + 1
                        } else if (page >= data.totalPages - 2) {
                          pageNum = data.totalPages - 4 + i
                        } else {
                          pageNum = page - 2 + i
                        }
                        return (
                          <Button
                            key={pageNum}
                            variant={page === pageNum ? 'default' : 'outline'}
                            size="sm"
                            className="w-9"
                            onClick={() => setPage(pageNum)}
                          >
                            {pageNum}
                          </Button>
                        )
                      })}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.min(data.totalPages, p + 1))}
                        disabled={page === data.totalPages}
                      >
                        Next
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage(data.totalPages)}
                        disabled={page === data.totalPages}
                      >
                        {'>>'}
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Notification Template</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this notification template? This action cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
