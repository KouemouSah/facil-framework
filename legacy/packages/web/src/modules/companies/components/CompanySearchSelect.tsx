"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Check, ChevronsUpDown, Building2, Search, Loader2, ShieldCheck } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Badge } from "@/components/ui/badge"
import { companiesAdminApi } from "../services/api"
import type { CompanySearchResult } from "../types"

interface CompanySearchSelectProps {
  value: string | null
  onValueChange: (id: string) => void
  placeholder?: string
  className?: string
}

export default function CompanySearchSelect({
  value,
  onValueChange,
  placeholder = "Seleccionar empresa...",
  className,
}: CompanySearchSelectProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<CompanySearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<CompanySearchResult | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const seqRef = useRef(0)

  // Fetch selected company on mount if value is set
  useEffect(() => {
    if (value && !selected) {
      companiesAdminApi.search(value, 1).then((res) => {
        const match = res.find((r) => r.id === value)
        if (match) setSelected(match)
      }).catch(() => {})
    }
  }, [value, selected])

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([])
      return
    }
    const seq = ++seqRef.current
    setLoading(true)
    try {
      const data = await companiesAdminApi.search(q, 10)
      if (seq === seqRef.current) setResults(data)
    } catch {
      if (seq === seqRef.current) setResults([])
    } finally {
      if (seq === seqRef.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(query), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, doSearch])

  const handleSelect = (company: CompanySearchResult) => {
    setSelected(company)
    setOpen(false)
    setQuery("")
    onValueChange(company.id)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("justify-between w-full", className)}
        >
          {selected ? (
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <Building2 className="h-4 w-4 shrink-0" />
              <span className="truncate">{selected.legal_name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                {selected.tax_id}
              </span>
              {selected.is_verified && (
                <ShieldCheck className="h-3 w-3 text-green-500 shrink-0" />
              )}
            </div>
          ) : (
            <span className="text-muted-foreground">{placeholder}</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <div className="flex flex-col">
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar por nombre, NIF o CIF..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
                autoFocus
              />
            </div>
          </div>
          <ScrollArea className="h-[250px]">
            {loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : query.length < 2 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                Ingrese al menos 2 caracteres
              </div>
            ) : results.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No se encontraron empresas
              </div>
            ) : (
              <div className="p-2">
                {results.map((company) => (
                  <div
                    key={company.id}
                    onClick={() => handleSelect(company)}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-md cursor-pointer transition-colors hover:bg-accent",
                      value === company.id && "bg-accent"
                    )}
                  >
                    <Check
                      className={cn(
                        "h-4 w-4 shrink-0",
                        value === company.id ? "opacity-100" : "opacity-0"
                      )}
                    />
                    <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">
                        {company.legal_name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {company.tax_id}
                        {company.nif && ` • NIF: ${company.nif}`}
                        {company.city_name && ` • ${company.city_name}`}
                      </div>
                    </div>
                    {company.is_verified && (
                      <Badge variant="outline" className="text-xs shrink-0 text-green-600 border-green-300">
                        Verificada
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  )
}
