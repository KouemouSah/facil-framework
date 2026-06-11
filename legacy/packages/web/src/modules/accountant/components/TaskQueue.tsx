'use client'

import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  AlertCircle,
  Building,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  AlertTriangle,
  ArrowUpDown,
  Filter,
  TrendingUp,
} from 'lucide-react'
import { usePendingTasks } from '../hooks'
import type { TaskQueueFilters } from '../types'
import { formatCurrency, formatDate } from '@/core/utils'
import { cn } from '@/lib/utils'

interface TaskQueueProps {
  onTaskClick?: (declarationId: string) => void
  initialFilters?: TaskQueueFilters
  className?: string
  showFilters?: boolean
}

export const TaskQueue = ({
  onTaskClick,
  initialFilters,
  className,
  showFilters = true,
}: TaskQueueProps) => {
  const [filters, setFilters] = useState<TaskQueueFilters>(
    initialFilters || {
      status: 'all',
      priority: 'all',
      sortBy: 'dueDate',
      sortOrder: 'asc',
    }
  )

  const { data: tasks, isLoading, error } = usePendingTasks(filters)

  const handleFilterChange = (key: keyof TaskQueueFilters, value: TaskQueueFilters[keyof TaskQueueFilters]) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value === 'all' ? undefined : value,
    }))
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft':
        return 'bg-gray-500'
      case 'pending':
        return 'bg-yellow-500'
      case 'in_review':
        return 'bg-blue-500'
      default:
        return 'bg-gray-500'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'draft':
        return 'Borrador'
      case 'pending':
        return 'Pendiente'
      case 'in_review':
        return 'En revisión'
      default:
        return status
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'bg-red-500 text-white'
      case 'high':
        return 'bg-orange-500 text-white'
      case 'medium':
        return 'bg-yellow-500 text-black'
      case 'low':
        return 'bg-green-500 text-white'
      default:
        return 'bg-gray-500 text-white'
    }
  }

  const getPriorityLabel = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'Urgente'
      case 'high':
        return 'Alta'
      case 'medium':
        return 'Media'
      case 'low':
        return 'Baja'
      default:
        return priority
    }
  }

  const getActionIcon = (actionType?: string | null) => {
    switch (actionType) {
      case 'review':
        return <FileText className="h-4 w-4" />
      case 'approve':
        return <CheckCircle2 className="h-4 w-4" />
      case 'fix_errors':
        return <AlertCircle className="h-4 w-4" />
      case 'add_documents':
        return <FileText className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  const getActionLabel = (actionType?: string | null) => {
    switch (actionType) {
      case 'review':
        return 'Revisar'
      case 'approve':
        return 'Aprobar'
      case 'fix_errors':
        return 'Corregir errores'
      case 'add_documents':
        return 'Agregar documentos'
      default:
        return 'Acción requerida'
    }
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <p>Error loading tasks. Please try again.</p>
        </div>
      </Card>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Filters */}
      {showFilters && (
        <Card className="p-4">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Filtros</span>
            </div>

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
                  <SelectItem value="draft">Borrador</SelectItem>
                  <SelectItem value="pending">Pendiente</SelectItem>
                  <SelectItem value="in_review">En revisión</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.priority || 'all'}
                onValueChange={(value) => handleFilterChange('priority', value)}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Prioridad" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas</SelectItem>
                  <SelectItem value="urgent">Urgente</SelectItem>
                  <SelectItem value="high">Alta</SelectItem>
                  <SelectItem value="medium">Media</SelectItem>
                  <SelectItem value="low">Baja</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.sortBy || 'dueDate'}
                onValueChange={(value) => handleFilterChange('sortBy', value)}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="Ordenar por" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dueDate">Fecha vencimiento</SelectItem>
                  <SelectItem value="priority">Prioridad</SelectItem>
                  <SelectItem value="createdAt">Fecha creación</SelectItem>
                  <SelectItem value="amount">Monto</SelectItem>
                </SelectContent>
              </Select>

              <Button
                variant="outline"
                size="icon"
                onClick={() =>
                  handleFilterChange(
                    'sortOrder',
                    filters.sortOrder === 'asc' ? 'desc' : 'asc'
                  )
                }
              >
                <ArrowUpDown className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Task list */}
      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="space-y-3">
                <div className="h-5 bg-muted rounded w-1/3" />
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="h-4 bg-muted rounded w-1/2" />
              </div>
            </Card>
          ))}
        </div>
      ) : tasks && tasks.length > 0 ? (
        <div className="space-y-3">
          {tasks.map((task) => (
            <Card
              key={task.id}
              className={cn(
                'p-6 cursor-pointer transition-all duration-200 hover:shadow-lg hover:border-primary',
                task.requiresAction && 'border-l-4 border-l-orange-500'
              )}
              onClick={() => onTaskClick?.(task.id)}
            >
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                      <FileText className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold truncate">
                          {task.declarationType}
                        </h3>
                        <Badge className={getStatusColor(task.status)}>
                          {getStatusLabel(task.status)}
                        </Badge>
                        <Badge className={getPriorityColor(task.priority)}>
                          {getPriorityLabel(task.priority)}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Building className="h-4 w-4" />
                        <span className="truncate">{task.companyName}</span>
                      </div>
                    </div>
                  </div>

                  {/* Action required badge */}
                  {task.requiresAction && (
                    <Badge
                      variant="outline"
                      className="border-orange-500 text-orange-600 shrink-0"
                    >
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      {getActionLabel(task.actionType)}
                    </Badge>
                  )}
                </div>

                {/* Details grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {/* Due date */}
                  {task.dueDate && (
                    <div className="flex items-start gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-xs text-muted-foreground">
                          Vencimiento
                        </p>
                        <p className="text-sm font-medium">
                          {formatDate(task.dueDate)}
                        </p>
                        {task.daysUntilDue !== null &&
                          task.daysUntilDue !== undefined && (
                            <p
                              className={cn(
                                'text-xs',
                                task.daysUntilDue < 0
                                  ? 'text-red-600'
                                  : task.daysUntilDue <= 3
                                  ? 'text-orange-600'
                                  : 'text-green-600'
                              )}
                            >
                              {task.daysUntilDue < 0
                                ? `${Math.abs(task.daysUntilDue)}d vencido`
                                : `${task.daysUntilDue}d restantes`}
                            </p>
                          )}
                      </div>
                    </div>
                  )}

                  {/* Amount */}
                  {task.amount && (
                    <div className="flex items-start gap-2">
                      <TrendingUp className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-xs text-muted-foreground">Monto</p>
                        <p className="text-sm font-semibold">
                          {formatCurrency(task.amount)}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Created date */}
                  <div className="flex items-start gap-2">
                    <Clock className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">Creado</p>
                      <p className="text-sm font-medium">
                        {formatDate(task.createdAt)}
                      </p>
                    </div>
                  </div>

                  {/* Last updated */}
                  <div className="flex items-start gap-2">
                    <ArrowUpDown className="h-4 w-4 text-muted-foreground mt-0.5" />
                    <div>
                      <p className="text-xs text-muted-foreground">
                        Actualizado
                      </p>
                      <p className="text-sm font-medium">
                        {formatDate(task.updatedAt)}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Action button */}
                {task.requiresAction && (
                  <div className="flex items-center justify-end">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation()
                        onTaskClick?.(task.id)
                      }}
                    >
                      {getActionIcon(task.actionType)}
                      <span className="ml-2">{getActionLabel(task.actionType)}</span>
                    </Button>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-12">
          <div className="text-center text-muted-foreground">
            <CheckCircle2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No hay tareas pendientes</p>
            <p className="text-sm">
              No se encontraron tareas con los filtros aplicados.
            </p>
          </div>
        </Card>
      )}

      {/* Summary */}
      {tasks && tasks.length > 0 && (
        <Card className="p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              Total de tareas: <span className="font-semibold">{tasks.length}</span>
            </span>
            <div className="flex items-center gap-4">
              <span className="text-muted-foreground">
                Requieren acción:{' '}
                <span className="font-semibold text-orange-600">
                  {tasks.filter((t) => t.requiresAction).length}
                </span>
              </span>
              <span className="text-muted-foreground">
                Urgentes:{' '}
                <span className="font-semibold text-red-600">
                  {tasks.filter((t) => t.priority === 'urgent').length}
                </span>
              </span>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
