/**
 * USSD Configurations List Page
 * Admin page for managing USSD configurations for mobile operators
 */

'use client'

import { useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useTranslations } from 'next-intl'
import { Plus, Edit, Trash2, Power, PowerOff } from 'lucide-react'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useUssdConfigs,
  useDeleteUssdConfig,
} from '@/modules/communications/hooks/useUssdConfigs'
import type { UssdConfigResponse } from '@/modules/communications/types'

export default function UssdConfigsPage() {
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string
  const t = useTranslations('admin.ussd')
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const { data, isLoading } = useUssdConfigs()
  const deleteMutation = useDeleteUssdConfig()

  const handleDelete = async () => {
    if (deleteId) {
      await deleteMutation.mutateAsync(deleteId)
      setDeleteId(null)
    }
  }

  const getOperatorName = (operator: string) => {
    const operatorKey = operator as 'getesa' | 'muni' | 'other_api_sms'
    return t(`operators.${operatorKey}`)
  }

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="text-muted-foreground">
            {t('description')}
          </p>
        </div>
        <Button onClick={() => router.push(`/${locale}/dashboard/admin/communications/ussd/new`)}>
          <Plus className="mr-2 h-4 w-4" />
          {t('newConfig')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('cardTitle')}</CardTitle>
          <CardDescription>
            {t('configsCount', { count: data?.total || 0 })}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8">{t('loading')}</div>
          ) : !data?.configs.length ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('noConfigs')}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('operator')}</TableHead>
                  <TableHead>{t('shortCode')}</TableHead>
                  <TableHead>{t('operatorCode')}</TableHead>
                  <TableHead>{t('menus')}</TableHead>
                  <TableHead>{t('timeout')}</TableHead>
                  <TableHead>{t('status')}</TableHead>
                  <TableHead className="text-right">{t('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.configs.map((config: UssdConfigResponse) => (
                  <TableRow key={config.id}>
                    <TableCell className="font-medium">
                      {getOperatorName(config.operatorName)}
                    </TableCell>
                    <TableCell>
                      <code className="px-2 py-1 bg-muted rounded">{config.shortCode}</code>
                    </TableCell>
                    <TableCell>{config.operatorCode}</TableCell>
                    <TableCell>{t('menusCount', { count: config.menuStructure.length })}</TableCell>
                    <TableCell>{t('timeoutValue', { seconds: config.sessionTimeoutSeconds })}</TableCell>
                    <TableCell>
                      {config.isActive ? (
                        <Badge variant="default" className="gap-1">
                          <Power className="h-3 w-3" />
                          {t('active')}
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="gap-1">
                          <PowerOff className="h-3 w-3" />
                          {t('inactive')}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          router.push(`/${locale}/dashboard/admin/communications/ussd/${config.id}/edit`)
                        }
                      >
                        <Edit className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteId(config.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('confirmDelete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteWarning')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete}>{t('delete')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
