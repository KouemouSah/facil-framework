/**
 * SmsTemplateList Component
 * Displays a list of SMS templates with filtering and actions
 */

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Plus, Edit, Trash2, MessageCircle, Filter, CheckCircle, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
import { useSmsTemplatesList, useDeleteSmsTemplate } from '../hooks/useSmsTemplates'
import type { SmsTemplateCategory } from '../types'

interface SmsTemplateListProps {
  locale: string
}

export function SmsTemplateList({ locale }: SmsTemplateListProps) {
  const router = useRouter()
  const t = useTranslations('admin.smsTemplates')
  const tCategories = useTranslations('admin.emailTemplates.categories')
  const tCommon = useTranslations('common')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [category, setCategory] = useState<SmsTemplateCategory | 'all'>('all')
  const [isActive, setIsActive] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)

  const { data, isLoading, error } = useSmsTemplatesList({
    page,
    pageSize,
    category: category !== 'all' ? category : undefined,
    isActive,
  })

  const handlePageSizeChange = (newSize: string) => {
    setPageSize(Number(newSize))
    setPage(1) // Reset to first page when changing page size
  }

  const deleteMutation = useDeleteSmsTemplate()

  const handleDelete = async () => {
    if (deleteId) {
      await deleteMutation.mutateAsync(deleteId)
      setDeleteId(null)
    }
  }

  const getCategoryBadge = (category: string) => {
    const colors: Record<string, string> = {
      auth: 'bg-blue-100 text-blue-800 border-blue-200',
      notifications: 'bg-purple-100 text-purple-800 border-purple-200',
      payments: 'bg-green-100 text-green-800 border-green-200',
      payment: 'bg-green-100 text-green-800 border-green-200',
      declarations: 'bg-orange-100 text-orange-800 border-orange-200',
      reminders: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      alerts: 'bg-red-100 text-red-800 border-red-200',
      request: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      requests: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      appointment: 'bg-cyan-100 text-cyan-800 border-cyan-200',
      document: 'bg-teal-100 text-teal-800 border-teal-200',
      security: 'bg-rose-100 text-rose-800 border-rose-200',
      system: 'bg-gray-100 text-gray-800 border-gray-200',
    }

    return (
      <Badge variant="outline" className={colors[category] || 'bg-gray-100 text-gray-800 border-gray-200'}>
        {tCategories(category)}
      </Badge>
    )
  }

  const truncateContent = (content: string, maxLength: number = 50): string => {
    if (content.length <= maxLength) return content
    return content.substring(0, maxLength) + '...'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">SMS Templates</h1>
          <p className="text-muted-foreground">
            Manage SMS templates for notifications and alerts
          </p>
        </div>
        <Button onClick={() => router.push(`/${locale}/dashboard/admin/communications/sms-templates/new`)}>
          <Plus className="mr-2 h-4 w-4" />
          New Template
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
          <CardDescription>Filter SMS templates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('category') || 'Category'}</label>
              <Select
                value={category}
                onValueChange={(value) => setCategory(value as SmsTemplateCategory | 'all')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{tCommon('all')}</SelectItem>
                  <SelectItem value="auth">{tCategories('auth')}</SelectItem>
                  <SelectItem value="notifications">{tCategories('notifications')}</SelectItem>
                  <SelectItem value="payments">{tCategories('payments')}</SelectItem>
                  <SelectItem value="payment">{tCategories('payment')}</SelectItem>
                  <SelectItem value="declarations">{tCategories('declarations')}</SelectItem>
                  <SelectItem value="request">{tCategories('request')}</SelectItem>
                  <SelectItem value="requests">{tCategories('requests')}</SelectItem>
                  <SelectItem value="appointment">{tCategories('appointment')}</SelectItem>
                  <SelectItem value="document">{tCategories('document')}</SelectItem>
                  <SelectItem value="security">{tCategories('security')}</SelectItem>
                  <SelectItem value="reminders">{tCategories('reminders')}</SelectItem>
                  <SelectItem value="alerts">{tCategories('alerts')}</SelectItem>
                  <SelectItem value="system">{tCategories('system')}</SelectItem>
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
                  setCategory('all')
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
                <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No templates found</p>
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => router.push(`/${locale}/dashboard/admin/communications/sms-templates/new`)}
                >
                  Create your first template
                </Button>
              </div>
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Code</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Content Preview</TableHead>
                    <TableHead>Segments</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.templates.map((template) => (
                    <TableRow key={template.id}>
                      <TableCell className="font-mono text-sm">{template.templateCode}</TableCell>
                      <TableCell>
                        <div className="font-medium">{template.nameEs}</div>
                      </TableCell>
                      <TableCell>{getCategoryBadge(template.category)}</TableCell>
                      <TableCell className="max-w-xs">
                        <div className="text-sm text-muted-foreground">
                          {truncateContent(template.contentEs, 60)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {template.contentEsSegments || 1} / {template.maxSegments}
                        </Badge>
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
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/${locale}/dashboard/admin/communications/sms-templates/${template.id}/edit`)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
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
            <AlertDialogTitle>Delete SMS Template</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this SMS template? This action cannot be
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
