'use client'

/**
 * ONRC Agent — National Company Lookup (enriched)
 *
 * Features:
 * - Search by NIF, PE-XXXX, or company name (debounced 300ms)
 * - Enriched result cards (forma, commerce_type, zone, verified badge)
 * - Recent searches history (localStorage, last 10)
 * - Print-friendly company card (window.print with @media print)
 * - Badge verified/unverified + active/inactive
 */

import { useCallback, useRef, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  Search, Building2, ShieldCheck, ShieldX, MapPin, FileText,
  Clock, Printer, X, History, Briefcase, Tag,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { companyMinistryApi } from '@/modules/companies/services/api'
import type { LookupResult } from '@/modules/companies/types'
import { PrintHeader, PrintFooter } from '@/components/shared/PrintHeader'

const REGIME_COLORS: Record<string, string> = {
  bundle: 'bg-green-100 text-green-800',
  declarativo: 'bg-blue-100 text-blue-800',
  exento: 'bg-gray-100 text-gray-700',
  pendiente: 'bg-yellow-100 text-yellow-800',
}

const HISTORY_KEY = 'onrc_lookup_history'
const MAX_HISTORY = 10

type HistoryEntry = { query: string; timestamp: number; resultCount: number }

export default function ONRCLookupPage() {
  const t = useTranslations('agent')

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<LookupResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const debounceRef = useRef<NodeJS.Timeout>()
  const seqRef = useRef(0)

  // Recent searches (localStorage)
  const [history, setHistory] = useState<HistoryEntry[]>(() => {
    if (typeof window === 'undefined') return []
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') }
    catch { return [] }
  })

  const addToHistory = useCallback((q: string, count: number) => {
    setHistory(prev => {
      const next = [{ query: q, timestamp: Date.now(), resultCount: count }, ...prev.filter(h => h.query !== q)].slice(0, MAX_HISTORY)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  const clearHistory = () => {
    setHistory([])
    localStorage.removeItem(HISTORY_KEY)
  }

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([])
      setSearched(false)
      return
    }
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const res = await companyMinistryApi.lookup(q)
      if (seq === seqRef.current) {
        setResults(res.results)
        setSearched(true)
        addToHistory(q, res.count)
      }
    } catch {
      if (seq === seqRef.current) {
        setResults([])
        setSearched(true)
      }
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [addToHistory])

  const handleChange = (val: string) => {
    setQuery(val)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(val), 300)
  }

  const handleHistoryClick = (q: string) => {
    setQuery(q)
    doSearch(q)
  }

  const handlePrint = (companyId: string) => {
    setSelectedId(companyId)
    setTimeout(() => window.print(), 100)
  }

  const selected = selectedId ? results.find(c => c.id === selectedId) : null

  return (
    <>
      {/* Print-only company card */}
      {selected && (
        <div className="hidden print:block p-4 max-w-lg mx-auto">
          <PrintHeader
            title="Ficha Empresa"
            subtitle="ONRC"
            meta={[
              ...(selected.nif ? [{ label: 'NIF', value: selected.nif }] : []),
              ...(selected.zone_code ? [{ label: 'Zona', value: selected.zone_code }] : []),
            ]}
          />
          <div className="space-y-1.5 text-[9pt] mt-3">
            <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Razón Social:</span><span>{selected.legal_name}</span></div>
            {selected.nif && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">NIF:</span><span className="font-mono">{selected.nif}</span></div>}
            {selected.registration_number && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">N° Registro:</span><span className="font-mono">{selected.registration_number}</span></div>}
            {selected.forma_juridica && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Forma Jurídica:</span><span>{selected.forma_juridica}</span></div>}
            {selected.regimen_fiscal && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Régimen Fiscal:</span><span>{selected.regimen_fiscal}</span></div>}
            {selected.commerce_type && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Tipo Comercio:</span><span>{selected.commerce_type}</span></div>}
            {selected.city_name && <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Ciudad:</span><span>{selected.city_name}</span></div>}
            <div className="flex justify-between border-b border-gray-100 pb-1"><span className="font-medium">Estado:</span><span>{selected.is_active ? 'Activa' : 'Inactiva'}</span></div>
            <div className="flex justify-between"><span className="font-medium">Verificada:</span><span>{selected.is_verified ? 'Sí' : 'No'}</span></div>
          </div>
          <PrintFooter />
        </div>
      )}

      {/* Screen content */}
      <div className="flex flex-col items-center max-w-3xl mx-auto h-[calc(100vh-8rem)] overflow-y-auto print:hidden">
        {/* Header */}
        <div className="text-center mb-6">
          <Building2 className="h-10 w-10 mx-auto mb-2 text-primary" />
          <h1 className="text-2xl font-bold">{t('companyLookup.title')}</h1>
          <p className="text-muted-foreground mt-1 text-sm">{t('companyLookup.subtitle')}</p>
        </div>

        {/* Search */}
        <div className="relative w-full max-w-xl mb-4">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => handleChange(e.target.value)}
            placeholder={t('companyLookup.searchPlaceholder')}
            className="pl-12 h-14 text-lg rounded-xl"
            autoFocus
          />
          {loading && (
            <div className="absolute right-4 top-1/2 -translate-y-1/2">
              <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          )}
        </div>

        {/* Recent searches */}
        {!searched && history.length > 0 && (
          <div className="w-full max-w-xl mb-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-muted-foreground flex items-center gap-1"><History className="h-3 w-3" />Búsquedas recientes</span>
              <Button variant="ghost" size="sm" className="h-6 text-[10px] text-muted-foreground" onClick={clearHistory}>
                <X className="h-3 w-3 mr-0.5" />Limpiar
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {history.map(h => (
                <button
                  key={h.query}
                  onClick={() => handleHistoryClick(h.query)}
                  className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border hover:bg-muted transition-colors"
                >
                  <Clock className="h-3 w-3 text-muted-foreground" />
                  <span>{h.query}</span>
                  <Badge variant="secondary" className="text-[9px] px-1 py-0">{h.resultCount}</Badge>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* No results */}
        {searched && results.length === 0 && !loading && (
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-10 w-10 mx-auto mb-2 opacity-30" />
            <p>{t('companyLookup.noResults')}</p>
          </div>
        )}

        {/* Results */}
        {searched && results.length > 0 && (
          <p className="text-xs text-muted-foreground mb-3 w-full">{results.length} resultado(s) para &quot;{query}&quot;</p>
        )}

        <div className="w-full space-y-3">
          {results.map(c => (
            <Card key={c.id} className="hover:shadow-md transition-shadow">
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  {c.is_verified ? (
                    <ShieldCheck className="h-5 w-5 text-green-600 shrink-0" />
                  ) : (
                    <ShieldX className="h-5 w-5 text-yellow-600 shrink-0" />
                  )}
                  <span className="truncate">{c.legal_name}</span>
                  <div className="flex items-center gap-1.5 ml-auto shrink-0">
                    {c.regimen_fiscal && (
                      <Badge className={`${REGIME_COLORS[c.regimen_fiscal] || 'bg-gray-100'}`}>
                        {c.regimen_fiscal}
                      </Badge>
                    )}
                    <Badge variant={c.is_active ? 'default' : 'destructive'} className="text-xs">
                      {c.is_active ? t('companyLookup.active') : t('companyLookup.inactive')}
                    </Badge>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent className="pb-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1.5 text-sm">
                  {c.nif && (
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground text-xs">NIF:</span>
                      <span className="font-mono font-medium text-xs">{c.nif}</span>
                    </div>
                  )}
                  {c.registration_number && (
                    <div className="flex items-center gap-1.5">
                      <FileText className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-muted-foreground text-xs">Reg:</span>
                      <span className="font-mono font-medium text-xs">{c.registration_number}</span>
                    </div>
                  )}
                  {c.forma_juridica && (
                    <div className="flex items-center gap-1.5">
                      <Tag className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-xs">{c.forma_juridica}</span>
                    </div>
                  )}
                  {c.commerce_type && (
                    <div className="flex items-center gap-1.5">
                      <Briefcase className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-xs">{c.commerce_type}</span>
                    </div>
                  )}
                  {c.city_name && (
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-3 w-3 text-muted-foreground shrink-0" />
                      <span className="text-xs">{c.city_name}</span>
                    </div>
                  )}
                  {c.zone_code && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-muted-foreground text-xs">Zona:</span>
                      <Badge variant="outline" className="text-[10px]">{c.zone_code}</Badge>
                    </div>
                  )}
                </div>
                {/* Actions */}
                <div className="flex items-center gap-2 mt-3 pt-2 border-t">
                  <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={() => handlePrint(c.id)}>
                    <Printer className="h-3 w-3" />Imprimir ficha
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </>
  )
}
