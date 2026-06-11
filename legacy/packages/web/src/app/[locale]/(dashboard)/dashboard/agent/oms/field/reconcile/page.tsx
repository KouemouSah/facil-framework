'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale } from 'next-intl'
import { useToast } from '@/hooks/use-toast'
import { ArrowLeft, Wallet, Receipt } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { inspectionApi } from '@/modules/inspections/services/api'
import { fmtXAF } from '@/modules/inspections/utils/formatters'
import type { ReconciliationResponse } from '@/modules/inspections/types'

export default function ReconcilePage() {
  const locale = useLocale()
  const router = useRouter()
  const { toast } = useToast()
  const [data, setData] = useState<ReconciliationResponse | null>(null)
  const [loading, setLoading] = useState(true)

  const today = new Date().toISOString().split('T')[0]

  const fetchData = useCallback(async () => {
    try {
      setLoading(true)
      const result = await inspectionApi.getReconciliation(today)
      setData(result)
    } catch {
      toast({ title: 'Error', variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [today, toast])

  useEffect(() => { fetchData() }, [fetchData])

  return (
    <div className="flex flex-col gap-4 p-4 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <Wallet className="h-6 w-6 text-amber-600" />
        <h1 className="text-xl font-bold">Reconciliación</h1>
        <span className="text-sm text-muted-foreground ml-auto">
          {new Date(today).toLocaleDateString(locale === 'fr' ? 'fr-FR' : locale === 'en' ? 'en-US' : 'es-ES')}
        </span>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-3">
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-600">
              {fmtXAF(data?.total_amount ?? 0, locale)}
            </p>
            <p className="text-xs text-muted-foreground">Cash cobrado hoy</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold">{data?.total_count ?? 0}</p>
            <p className="text-xs text-muted-foreground">Transacciones</p>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Cobros del día</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-2">
              {[1, 2, 3].map(i => <div key={i} className="h-10 bg-muted animate-pulse rounded" />)}
            </div>
          ) : !data || data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">
              Ningún cobro registrado hoy.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>#</TableHead>
                  <TableHead>Hora</TableHead>
                  <TableHead>Empresa</TableHead>
                  <TableHead className="text-right">Monto</TableHead>
                  <TableHead>Recibo</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((item, idx) => (
                  <TableRow key={item.id}>
                    <TableCell>{idx + 1}</TableCell>
                    <TableCell className="text-xs">
                      {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </TableCell>
                    <TableCell>
                      <div>
                        <span className="font-medium text-sm">{item.company_name}</span>
                        <br />
                        <span className="text-xs text-muted-foreground">{item.company_nif}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-right font-medium">
                      {fmtXAF(item.payment_amount ?? 0, locale)}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-xs">
                        <Receipt className="h-3 w-3" />
                        {item.payment_receipt_number}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* SLA Warning */}
      {data && data.total_count > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-3 text-sm text-amber-800">
            <strong>Rappel :</strong> Le cash collecté doit être reversé au Trésor dans les 48h.
            Contactez votre superviseur pour le reversement.
          </CardContent>
        </Card>
      )}
    </div>
  )
}
