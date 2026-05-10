'use client'

/**
 * Treasury Validation History — Read-only view of validated/rejected payments
 *
 * Dedicated history page for AYUNTAMIENTO/CAMARA agents.
 * Shows completed payments with validation details, amounts, dates.
 * No action buttons (validate/reject) — this is audit/history only.
 *
 * @route /[locale]/dashboard/agent/treasury/validation/history
 */

import { useEffect, useRef, useState } from 'react'
import {
  History, Search, ChevronLeft, ChevronRight, Building2, RefreshCw,
  Eye, CheckCircle2, XCircle, DollarSign, Calendar, CreditCard,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { useTranslations } from 'next-intl'
import { useLocale } from 'next-intl'
import { usePendingPayments } from '@/modules/treasury/hooks'
import type { PendingPayment } from '@/modules/treasury/types'

function fmtXAF(n: number | null | undefined, locale = 'es-GQ'): string {
  if (n == null || isNaN(n)) return '0 XAF'
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n) + ' XAF'
}

function fmtDate(dateStr: string | null | undefined, locale = 'es-GQ'): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    })
  } catch { return dateStr }
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
}

const METHOD_LABELS: Record<string, string> = {
  cash: 'Efectivo',
  check: 'Cheque',
  bank_transfer: 'Transferencia',
  mobile_money: 'Mobile Money',
  card: 'Tarjeta',
}

export default function TreasuryValidationHistoryPage() {
  const t = useTranslations('treasury')
  const locale = useLocale()

  const [page, setPage] = useState(1)
  const [methodFilter, setMethodFilter] = useState('all')
  const PAGE_SIZE = 20

  const debounceRef = useRef<NodeJS.Timeout>()
  const [searchInput, setSearchInput] = useState('')
  const [_search, setSearch] = useState('')
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => { setSearch(searchInput); setPage(1) }, 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  const { data: paymentsData, isLoading, refetch } = usePendingPayments({
    status: 'completed',
    method: methodFilter !== 'all' ? methodFilter : undefined,
    page,
    pageSize: PAGE_SIZE,
  })

  const payments = paymentsData?.payments ?? []
  const total = paymentsData?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)

  const [detailPayment, setDetailPayment] = useState<PendingPayment | null>(null)

  const totalValidated = payments.filter(p => p.workflowStatus === 'completed').length
  const totalRejected = payments.filter(p => p.workflowStatus === 'rejected').length
  const totalAmount = payments.reduce((sum, p) => sum + (p.totalAmount || 0), 0)

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <History className="h-5 w-5 text-blue-600" />
            {t('history.title', { defaultValue: 'Historial de Validaciones' })}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t('history.subtitle', { defaultValue: 'Pagos validados y rechazados por su entidad' })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-xs">{total} {t('history.records', { defaultValue: 'registros' })}</Badge>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t('history.validated', { defaultValue: 'Validados' })}</p>
              <p className="text-2xl font-bold text-green-700">{totalValidated}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t('history.rejected', { defaultValue: 'Rechazados' })}</p>
              <p className="text-2xl font-bold text-red-700">{totalRejected}</p>
            </div>
          </div>
        </Card>
        <Card className="p-3">
          <div className="flex items-center gap-2">
            <DollarSign className="h-5 w-5 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">{t('history.totalAmount', { defaultValue: 'Monto Total' })}</p>
              <p className="text-lg font-bold">{fmtXAF(totalAmount, locale)}</p>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input value={searchInput} onChange={e => setSearchInput(e.target.value)}
            placeholder={t('history.searchPlaceholder', { defaultValue: 'Buscar por referencia, empresa...' })}
            className="pl-8 h-8 text-xs" />
        </div>
        <Select value={methodFilter} onValueChange={v => { setMethodFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[140px] h-8 text-xs">
            <SelectValue placeholder={t('history.allMethods', { defaultValue: 'Todos' })} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t('history.allMethods', { defaultValue: 'Todos' })}</SelectItem>
            <SelectItem value="cash">{t('history.cash', { defaultValue: 'Efectivo' })}</SelectItem>
            <SelectItem value="check">{t('history.check', { defaultValue: 'Cheque' })}</SelectItem>
            <SelectItem value="bank_transfer">{t('history.transfer', { defaultValue: 'Transferencia' })}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">{t('history.reference', { defaultValue: 'Referencia' })}</TableHead>
                <TableHead className="text-xs">{t('history.company', { defaultValue: 'Empresa' })}</TableHead>
                <TableHead className="text-xs w-[100px]">{t('history.method', { defaultValue: 'Método' })}</TableHead>
                <TableHead className="text-xs w-[110px] text-right">{t('history.amount', { defaultValue: 'Monto' })}</TableHead>
                <TableHead className="text-xs w-[130px]">{t('history.date', { defaultValue: 'Fecha' })}</TableHead>
                <TableHead className="text-xs w-[95px]">{t('history.status', { defaultValue: 'Estado' })}</TableHead>
                <TableHead className="text-xs w-[40px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow><TableCell colSpan={7} className="text-center py-8 text-muted-foreground">...</TableCell></TableRow>
              ) : payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                    <History className="h-8 w-8 mx-auto mb-2 opacity-30" />
                    <p>{t('history.noRecords', { defaultValue: 'Sin registros de validación' })}</p>
                  </TableCell>
                </TableRow>
              ) : payments.map(payment => {
                const statusColor = STATUS_COLORS[payment.workflowStatus] || 'bg-gray-100 text-gray-800'
                return (
                  <TableRow key={payment.id} className="hover:bg-muted/30">
                    <TableCell className="text-xs font-mono">{payment.paymentReference || payment.id?.slice(0, 12)}</TableCell>
                    <TableCell className="text-xs">
                      <div className="flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="truncate max-w-[180px]">{payment.companyName || payment.userName || '—'}</span>
                      </div>
                      {payment.workflowCode && (
                        <span className="text-[10px] text-muted-foreground">{payment.workflowCode}</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs">
                      <div className="flex items-center gap-1">
                        <CreditCard className="h-3 w-3 text-muted-foreground" />
                        {METHOD_LABELS[payment.paymentMethod] || payment.paymentMethod}
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-right font-mono font-bold">
                      {fmtXAF(payment.totalAmount, locale)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {fmtDate(payment.validatedAt || payment.updatedAt, locale)}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={`text-[10px] ${statusColor}`}>
                        {payment.workflowStatus === 'completed' ? '✓ Validado' : '✕ Rechazado'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-7 w-7"
                        onClick={() => setDetailPayment(payment)}>
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground text-xs">{page}/{totalPages}</span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      <Sheet open={!!detailPayment} onOpenChange={open => { if (!open) setDetailPayment(null) }}>
        <SheetContent side="right" className="w-[400px] sm:w-[480px] overflow-y-auto">
          {detailPayment && (
            <>
              <SheetHeader>
                <SheetTitle className="flex items-center gap-2">
                  <CreditCard className="h-4 w-4" />
                  {detailPayment.paymentReference || 'Pago'}
                </SheetTitle>
                <SheetDescription>
                  {detailPayment.workflowCode} · {METHOD_LABELS[detailPayment.paymentMethod] || detailPayment.paymentMethod}
                </SheetDescription>
              </SheetHeader>
              <div className="space-y-4 mt-4 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <span className="text-muted-foreground">{t('history.amount', { defaultValue: 'Monto' })}:</span>
                    <br/><strong className="text-base">{fmtXAF(detailPayment.totalAmount, locale)}</strong>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('history.status', { defaultValue: 'Estado' })}:</span>
                    <br/>
                    <Badge className={`text-xs mt-1 ${STATUS_COLORS[detailPayment.workflowStatus] || ''}`}>
                      {detailPayment.workflowStatus === 'completed' ? '✓ Validado' : '✕ Rechazado'}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('history.company', { defaultValue: 'Empresa' })}:</span>
                    <br/><strong>{detailPayment.companyName || detailPayment.userName || '—'}</strong>
                    {detailPayment.registrationNumber && (
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        {t('history.registrationNumber', { defaultValue: 'N° Registro' })}: {detailPayment.registrationNumber}
                      </p>
                    )}
                  </div>
                  <div>
                    <span className="text-muted-foreground">{t('history.date', { defaultValue: 'Fecha' })}:</span>
                    <br/><strong>{fmtDate(detailPayment.validatedAt || detailPayment.updatedAt, locale)}</strong>
                  </div>
                </div>
                {detailPayment.assignedAgentName && (
                  <div className="p-2 bg-muted/30 rounded border text-xs">
                    <span className="text-muted-foreground">{t('history.validatedBy', { defaultValue: 'Validado por' })}:</span>{' '}
                    <strong>{detailPayment.assignedAgentName}</strong>
                  </div>
                )}
                {detailPayment.obligations && detailPayment.obligations.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t">
                    <p className="font-medium">{t('history.obligations', { defaultValue: 'Obligaciones' })} ({detailPayment.obligations.length})</p>
                    {detailPayment.obligations.map((ob, i) => (
                      <div key={i} className="flex justify-between text-[10px] py-0.5">
                        <span className="text-muted-foreground">{ob.name || ob.fee_type}</span>
                        <span className="font-mono">{fmtXAF(ob.amount, locale)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
