'use client'

import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Building,
  Search,
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  MapPin,
  ArrowUpDown,
} from 'lucide-react'
import { useAccountantClients, usePrefetchClient } from '../hooks'
import type { ClientFilters } from '../types'
import { formatCurrency, formatDate } from '@/core/utils'
import { cn } from '@/lib/utils'

interface ClientListProps {
  onClientSelect?: (companyId: string) => void
  initialFilters?: ClientFilters
  showSearch?: boolean
  showFilters?: boolean
  className?: string
}

export const ClientList = ({
  onClientSelect,
  initialFilters,
  showSearch = true,
  showFilters = true,
  className,
}: ClientListProps) => {
  const [filters, setFilters] = useState<ClientFilters>(initialFilters || {})
  const [searchQuery, setSearchQuery] = useState(filters.search || '')

  const { data, isLoading, error } = useAccountantClients(filters)
  const prefetchClient = usePrefetchClient()

  // Debounced search
  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    const timeoutId = setTimeout(() => {
      setFilters((prev) => ({ ...prev, search: value }))
    }, 500)
    return () => clearTimeout(timeoutId)
  }

  const handleFilterChange = (key: keyof ClientFilters, value: ClientFilters[keyof ClientFilters]) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
    }))
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-500'
      case 'inactive':
        return 'bg-gray-500'
      case 'suspended':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active':
        return 'Activo'
      case 'inactive':
        return 'Inactivo'
      case 'suspended':
        return 'Suspendido'
      default:
        return status
    }
  }

  const getPriorityColor = (daysUntilDue?: number) => {
    if (!daysUntilDue) return 'text-gray-500'
    if (daysUntilDue < 0) return 'text-red-600'
    if (daysUntilDue <= 3) return 'text-orange-600'
    if (daysUntilDue <= 7) return 'text-yellow-600'
    return 'text-green-600'
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <p>Error loading clients. Please try again.</p>
        </div>
      </Card>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header with search and filters */}
      {(showSearch || showFilters) && (
        <Card className="p-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            {/* Search */}
            {showSearch && (
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar clientes..."
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  className="pl-10"
                />
              </div>
            )}

            {/* Filters */}
            {showFilters && (
              <div className="flex flex-wrap gap-2">
                <Select
                  value={filters.status || 'all'}
                  onValueChange={(value) => handleFilterChange('status', value)}
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue placeholder="Estado" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos</SelectItem>
                    <SelectItem value="active">Activos</SelectItem>
                    <SelectItem value="inactive">Inactivos</SelectItem>
                    <SelectItem value="suspended">Suspendidos</SelectItem>
                  </SelectContent>
                </Select>

                <Select
                  value={filters.sortBy || 'name'}
                  onValueChange={(value) => handleFilterChange('sortBy', value)}
                >
                  <SelectTrigger className="w-[160px]">
                    <SelectValue placeholder="Ordenar" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="name">Nombre</SelectItem>
                    <SelectItem value="lastActivity">Última actividad</SelectItem>
                    <SelectItem value="pendingCount">Pendientes</SelectItem>
                    <SelectItem value="totalDue">Monto total</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Client list */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="space-y-3">
                <div className="h-6 bg-muted rounded" />
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="grid grid-cols-2 gap-2">
                  <div className="h-10 bg-muted rounded" />
                  <div className="h-10 bg-muted rounded" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : data?.clients.length === 0 ? (
        <Card className="p-12">
          <div className="text-center text-muted-foreground">
            <Building className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No hay clientes</p>
            <p className="text-sm">No se encontraron clientes con los filtros aplicados.</p>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {data?.clients.map((client) => (
            <Card
              key={client.id}
              className="p-6 cursor-pointer hover:shadow-lg transition-all duration-200 hover:border-primary"
              onClick={() => onClientSelect?.(client.id)}
              onMouseEnter={() => prefetchClient(client.id)}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                    <Building className="h-5 w-5 text-primary" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-semibold truncate">{client.legal_name}</h3>
                    <p className="text-sm text-muted-foreground">
                      NIF: {client.tax_id}
                    </p>
                  </div>
                </div>
                <Badge className={getStatusColor(client.stats.status)}>
                  {getStatusLabel(client.stats.status)}
                </Badge>
              </div>

              {/* Location */}
              {client.city_name && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
                  <MapPin className="h-4 w-4" />
                  <span>{client.city_name}</span>
                </div>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                {/* Pending declarations */}
                <div className="p-3 bg-orange-50 dark:bg-orange-950/20 rounded-lg">
                  <div className="flex items-center justify-between">
                    <Clock className="h-4 w-4 text-orange-600" />
                    <span className="text-lg font-bold text-orange-600">
                      {client.stats.pendingDeclarations}
                    </span>
                  </div>
                  <p className="text-xs text-orange-600 mt-1">Pendientes</p>
                </div>

                {/* Draft declarations */}
                <div className="p-3 bg-gray-50 dark:bg-gray-950/20 rounded-lg">
                  <div className="flex items-center justify-between">
                    <FileText className="h-4 w-4 text-gray-600" />
                    <span className="text-lg font-bold text-gray-600">
                      {client.stats.draftDeclarations}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 mt-1">Borradores</p>
                </div>

                {/* In review */}
                <div className="p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
                  <div className="flex items-center justify-between">
                    <ArrowUpDown className="h-4 w-4 text-blue-600" />
                    <span className="text-lg font-bold text-blue-600">
                      {client.stats.inReviewDeclarations}
                    </span>
                  </div>
                  <p className="text-xs text-blue-600 mt-1">En revisión</p>
                </div>

                {/* Approved this month */}
                <div className="p-3 bg-green-50 dark:bg-green-950/20 rounded-lg">
                  <div className="flex items-center justify-between">
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                    <span className="text-lg font-bold text-green-600">
                      {client.stats.approvedThisMonth}
                    </span>
                  </div>
                  <p className="text-xs text-green-600 mt-1">Aprobados</p>
                </div>
              </div>

              {/* Financial summary */}
              <div className="space-y-2 border-t pt-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Total debido:</span>
                  <span className="font-semibold">
                    {formatCurrency(client.stats.totalAmountDue)}
                  </span>
                </div>
                {client.stats.overdueAmount > 0 && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-red-600">Vencido:</span>
                    <span className="font-semibold text-red-600">
                      {formatCurrency(client.stats.overdueAmount)}
                    </span>
                  </div>
                )}
              </div>

              {/* Next deadline */}
              {client.stats.nextDeadline && (
                <div className="mt-3 p-3 bg-muted rounded-lg">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">
                        Próximo vencimiento:
                      </p>
                      <p className="text-sm font-medium truncate">
                        {client.stats.nextDeadline.declarationType}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(client.stats.nextDeadline.dueDate)}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={getPriorityColor(
                        client.stats.nextDeadline.daysUntilDue
                      )}
                    >
                      {client.stats.nextDeadline.daysUntilDue < 0
                        ? 'Vencido'
                        : `${client.stats.nextDeadline.daysUntilDue}d`}
                    </Badge>
                  </div>
                </div>
              )}

              {/* Last activity */}
              <div className="mt-3 text-xs text-muted-foreground">
                Última actividad: {formatDate(client.stats.lastActivityDate)}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination info */}
      {data && data.total > 0 && (
        <div className="text-center text-sm text-muted-foreground">
          Mostrando {data.clients.length} de {data.total} clientes
        </div>
      )}
    </div>
  )
}
