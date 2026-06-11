'use client'

import { useState, useEffect } from 'react'
import { Check, ChevronsUpDown, Building, Search, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { useManagedCompanies } from '../hooks'

interface ClientSwitcherProps {
  value?: string
  onValueChange?: (companyId: string) => void
  className?: string
  placeholder?: string
}

export const ClientSwitcher = ({
  value,
  onValueChange,
  className,
  placeholder = 'Seleccionar cliente...',
}: ClientSwitcherProps) => {
  const [open, setOpen] = useState(false)
  const [selectedValue, setSelectedValue] = useState(value)
  const [searchQuery, setSearchQuery] = useState('')

  const { data: companies, isLoading, error } = useManagedCompanies()

  useEffect(() => {
    setSelectedValue(value)
  }, [value])

  const handleSelect = (companyId: string) => {
    setSelectedValue(companyId)
    setOpen(false)
    setSearchQuery('')
    onValueChange?.(companyId)
  }

  const selectedCompany = companies?.find((c) => c.id === selectedValue)

  // Filter companies based on search query
  const filteredCompanies = companies?.filter((company) => {
    if (!searchQuery) return true
    const search = searchQuery.toLowerCase()
    return (
      company.legal_name.toLowerCase().includes(search) ||
      company.tax_id.toLowerCase().includes(search) ||
      company.city_name?.toLowerCase().includes(search)
    )
  })

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn('justify-between', className)}
        >
          {isLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Cargando...</span>
            </div>
          ) : selectedCompany ? (
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <Building className="h-4 w-4 shrink-0" />
              <span className="truncate">{selectedCompany.legal_name}</span>
              {selectedCompany.stats && selectedCompany.stats.pendingDeclarations > 0 && (
                <Badge variant="secondary" className="ml-auto shrink-0">
                  {selectedCompany.stats.pendingDeclarations}
                </Badge>
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
          {/* Search input */}
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar cliente..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Company list */}
          <ScrollArea className="h-[300px]">
            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : error ? (
              <div className="py-6 text-center text-sm text-destructive px-3">
                Error al cargar los clientes
              </div>
            ) : filteredCompanies && filteredCompanies.length > 0 ? (
              <div className="p-2">
                {filteredCompanies.map((company) => (
                  <div
                    key={company.id}
                    onClick={() => handleSelect(company.id)}
                    className={cn(
                      'flex items-center gap-3 p-3 rounded-md cursor-pointer transition-colors hover:bg-accent',
                      selectedValue === company.id && 'bg-accent'
                    )}
                  >
                    <Check
                      className={cn(
                        'h-4 w-4 shrink-0',
                        selectedValue === company.id
                          ? 'opacity-100'
                          : 'opacity-0'
                      )}
                    />
                    <Building className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">
                        {company.legal_name}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        NIF: {company.tax_id}
                        {company.city_name && ` • ${company.city_name}`}
                      </div>
                    </div>
                    {company.stats && (
                      <div className="flex items-center gap-1 shrink-0">
                        {company.stats.pendingDeclarations > 0 && (
                          <Badge variant="secondary" className="text-xs">
                            {company.stats.pendingDeclarations}
                          </Badge>
                        )}
                        {company.stats.overdueAmount > 0 && (
                          <Badge variant="destructive" className="text-xs">
                            Vencido
                          </Badge>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-muted-foreground px-3">
                No se encontraron clientes.
              </div>
            )}
          </ScrollArea>
        </div>
      </PopoverContent>
    </Popover>
  )
}
