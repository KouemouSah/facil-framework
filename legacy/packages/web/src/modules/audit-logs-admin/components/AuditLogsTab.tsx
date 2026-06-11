'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import {
  FileText, Search, X, ChevronLeft, ChevronRight,
  Activity, TrendingUp, Clock, RefreshCw, AlertTriangle,
} from 'lucide-react'
import { useAuditLogs, useAuditLogStats } from '../hooks/useAuditLogs'

const ACTION_COLORS: Record<string, string> = {
  payment_completed: 'bg-green-100 text-green-800',
  request_submitted: 'bg-blue-100 text-blue-800',
  request_approved: 'bg-green-100 text-green-800',
  request_rejected: 'bg-red-100 text-red-800',
  request_escalated: 'bg-orange-100 text-orange-800',
  document_uploaded: 'bg-indigo-100 text-indigo-800',
  document_validated: 'bg-green-100 text-green-800',
  user_registered: 'bg-blue-100 text-blue-800',
  sla_warning: 'bg-yellow-100 text-yellow-800',
  sla_breach: 'bg-red-100 text-red-800',
}

const PAGE_SIZE = 25

export function AuditLogsTab() {
  const t = useTranslations('admin.auditLogs')

  const [page, setPage] = useState(1)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  // Filters
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [actionFilter, setActionFilter] = useState<string>('all')
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('all')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Debounce search input (300ms)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(value)
      setPage(1)
    }, 300)
  }, [])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // React Query: paginated logs
  const { data: logsData, isLoading, error } = useAuditLogs({
    page,
    page_size: PAGE_SIZE,
    search: debouncedSearch || undefined,
    action: actionFilter !== 'all' ? actionFilter : undefined,
    entity_type: entityTypeFilter !== 'all' ? entityTypeFilter : undefined,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
  })

  // React Query: stats (for filter options)
  const { data: stats } = useAuditLogStats()

  const logs = logsData?.items || []
  const total = logsData?.total || 0
  const pages = logsData?.pages || 0

  const clearFilters = () => {
    setSearch('')
    setDebouncedSearch('')
    setActionFilter('all')
    setEntityTypeFilter('all')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const hasFilters = search || actionFilter !== 'all' || entityTypeFilter !== 'all' || startDate || endDate
  const actionTypes = stats ? Object.keys(stats.by_action).sort() : []
  const entityTypes = stats ? Object.keys(stats.by_entity_type).sort() : []

  return (
    <div className="space-y-4">
      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-xs text-muted-foreground">{t('totalLogs')}</p>
                  <p className="text-lg font-bold">{stats.total_logs.toLocaleString()}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-green-500" />
                <div>
                  <p className="text-xs text-muted-foreground">{t('actionTypes')}</p>
                  <p className="text-lg font-bold">{Object.keys(stats.by_action).length}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-purple-500" />
                <div>
                  <p className="text-xs text-muted-foreground">{t('entityTypes')}</p>
                  <p className="text-lg font-bold">{Object.keys(stats.by_entity_type).length}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3">
              <div className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-orange-500" />
                <div>
                  <p className="text-xs text-muted-foreground">{t('onThisPage')}</p>
                  <p className="text-lg font-bold">{logs.length} / {total}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardContent className="p-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder={t('searchPlaceholder')}
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                className="pl-10 h-9"
              />
            </div>
            <Select value={actionFilter} onValueChange={(v) => { setActionFilter(v); setPage(1) }}>
              <SelectTrigger className="w-full md:w-[200px] h-9">
                <SelectValue placeholder={t('action')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allActions')}</SelectItem>
                {actionTypes.map((a) => (
                  <SelectItem key={a} value={a}>{a.replace(/_/g, ' ')}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={entityTypeFilter} onValueChange={(v) => { setEntityTypeFilter(v); setPage(1) }}>
              <SelectTrigger className="w-full md:w-[180px] h-9">
                <SelectValue placeholder={t('entity')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allEntityTypes')}</SelectItem>
                {entityTypes.map((et) => (
                  <SelectItem key={et} value={et}>{et.replace(/_/g, ' ')}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="date" value={startDate}
              onChange={(e) => { setStartDate(e.target.value); setPage(1) }}
              className="w-auto h-9"
            />
            <Input
              type="date" value={endDate}
              onChange={(e) => { setEndDate(e.target.value); setPage(1) }}
              className="w-auto h-9"
            />
            {hasFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X className="h-4 w-4 mr-1" /> {t('clearFilters')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Logs table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">{t('loadingLogs')}</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-12 text-red-500 gap-2">
              <AlertTriangle className="h-5 w-5" />
              <span className="text-sm">{t('errorLoading')}</span>
            </div>
          ) : logs.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <span className="text-sm">{t('noLogs')}</span>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[140px]">{t('date')}</TableHead>
                  <TableHead className="w-[160px]">{t('action')}</TableHead>
                  <TableHead>{t('entity')}</TableHead>
                  <TableHead className="w-[120px]">{t('ipAddress')}</TableHead>
                  <TableHead className="w-[40px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {logs.map((log) => (
                  <React.Fragment key={log.id}>
                    <TableRow
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                    >
                      <TableCell className="text-xs text-muted-foreground">
                        {new Date(log.created_at).toLocaleString('es-GQ', {
                          day: '2-digit', month: '2-digit', year: '2-digit',
                          hour: '2-digit', minute: '2-digit',
                        })}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={`text-xs ${ACTION_COLORS[log.action] || 'bg-gray-100 text-gray-800'}`}
                        >
                          {log.action.replace(/_/g, ' ')}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className="text-muted-foreground">{log.entity_type}</span>
                        {log.entity_id && (
                          <span className="ml-1 text-xs text-muted-foreground/60 font-mono">
                            {log.entity_id.length > 12
                              ? `${log.entity_id.substring(0, 8)}...`
                              : log.entity_id}
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground font-mono">
                        {log.ip_address || '-'}
                      </TableCell>
                      <TableCell>
                        <ChevronRight
                          className={`h-4 w-4 text-muted-foreground transition-transform ${
                            expandedId === log.id ? 'rotate-90' : ''
                          }`}
                        />
                      </TableCell>
                    </TableRow>
                    {expandedId === log.id && (
                      <TableRow>
                        <TableCell colSpan={5} className="bg-muted/30 p-4">
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                            <div>
                              <span className="text-muted-foreground">ID:</span>{' '}
                              <span className="font-mono">{log.id}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">{t('userId')}:</span>{' '}
                              <span className="font-mono">{log.user_id || '-'}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">{t('entityId')}:</span>{' '}
                              <span className="font-mono">{log.entity_id}</span>
                            </div>
                            <div>
                              <span className="text-muted-foreground">{t('userAgent')}:</span>{' '}
                              <span className="truncate max-w-[200px] inline-block">
                                {log.user_agent || '-'}
                              </span>
                            </div>
                          </div>
                          {(log.old_values || log.new_values) && (
                            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
                              {log.old_values && (
                                <div>
                                  <p className="text-xs font-semibold text-red-600 mb-1">{t('oldValues')}</p>
                                  <pre className="text-[11px] bg-red-50 p-2 rounded overflow-x-auto max-h-40">
                                    {JSON.stringify(log.old_values, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {log.new_values && (
                                <div>
                                  <p className="text-xs font-semibold text-green-600 mb-1">{t('newValues')}</p>
                                  <pre className="text-[11px] bg-green-50 p-2 rounded overflow-x-auto max-h-40">
                                    {JSON.stringify(log.new_values, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <span className="text-xs text-muted-foreground">
              {t('pageOf', { page, pages, total })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline" size="icon" className="h-8 w-8"
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline" size="icon" className="h-8 w-8"
                disabled={page >= pages}
                onClick={() => setPage(p => Math.min(pages, p + 1))}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
