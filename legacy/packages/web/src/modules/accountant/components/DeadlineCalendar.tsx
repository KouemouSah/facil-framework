'use client'

import { useState, useMemo } from 'react'
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
  Calendar,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Clock,
  TrendingUp,
} from 'lucide-react'
import { useUpcomingDeadlines, useOverdueDeadlines } from '../hooks'
import type { GetDeadlinesParams } from '../types'
import { formatCurrency, formatDate } from '@/core/utils'
import { cn } from '@/lib/utils'
import {
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  format,
  addMonths,
  subMonths,
  isSameMonth,
  isToday,
  parseISO,
  startOfWeek,
  endOfWeek,
} from 'date-fns'
import { es } from 'date-fns/locale'

interface DeadlineCalendarProps {
  onDeadlineClick?: (declarationId: string) => void
  companyId?: string
  className?: string
}

export const DeadlineCalendar = ({
  onDeadlineClick,
  companyId,
  className,
}: DeadlineCalendarProps) => {
  const [currentDate, setCurrentDate] = useState(new Date())
  const [view, setView] = useState<'month' | 'week' | 'list'>('month')

  const params: GetDeadlinesParams = useMemo(() => {
    const start = startOfMonth(currentDate)
    const end = endOfMonth(currentDate)
    return {
      startDate: format(start, 'yyyy-MM-dd'),
      endDate: format(end, 'yyyy-MM-dd'),
      ...(companyId && { companyId }),
    }
  }, [currentDate, companyId])

  const { data: deadlines, isLoading, error } = useUpcomingDeadlines(params)
  const { data: overdueDeadlines } = useOverdueDeadlines()

  // Group deadlines by date
  const deadlinesByDate = useMemo(() => {
    const map = new Map<string, typeof deadlines>()
    deadlines?.forEach((deadline) => {
      const dateKey = format(parseISO(deadline.dueDate), 'yyyy-MM-dd')
      const existing = map.get(dateKey) || []
      map.set(dateKey, [...existing, deadline])
    })
    return map
  }, [deadlines])

  // Calendar days
  const calendarDays = useMemo(() => {
    const start = startOfWeek(startOfMonth(currentDate), { locale: es })
    const end = endOfWeek(endOfMonth(currentDate), { locale: es })
    return eachDayOfInterval({ start, end })
  }, [currentDate])

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'bg-red-500'
      case 'high':
        return 'bg-orange-500'
      case 'medium':
        return 'bg-yellow-500'
      case 'low':
        return 'bg-green-500'
      default:
        return 'bg-gray-500'
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

  const handlePreviousMonth = () => {
    setCurrentDate(subMonths(currentDate, 1))
  }

  const handleNextMonth = () => {
    setCurrentDate(addMonths(currentDate, 1))
  }

  const handleToday = () => {
    setCurrentDate(new Date())
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 text-destructive">
          <AlertCircle className="h-5 w-5" />
          <p>Error loading deadlines. Please try again.</p>
        </div>
      </Card>
    )
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <Card className="p-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          {/* Navigation */}
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon" onClick={handlePreviousMonth}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <div className="min-w-[200px] text-center">
              <h2 className="text-lg font-semibold capitalize">
                {format(currentDate, 'MMMM yyyy', { locale: es })}
              </h2>
            </div>
            <Button variant="outline" size="icon" onClick={handleNextMonth}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" onClick={handleToday}>
              Hoy
            </Button>
          </div>

          {/* View selector */}
          <Select value={view} onValueChange={(v: 'month' | 'week' | 'list') => setView(v)}>
            <SelectTrigger className="w-[140px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="month">Mes</SelectItem>
              <SelectItem value="week">Semana</SelectItem>
              <SelectItem value="list">Lista</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </Card>

      {/* Overdue alerts */}
      {overdueDeadlines && overdueDeadlines.length > 0 && (
        <Card className="p-4 border-red-500 bg-red-50 dark:bg-red-950/20">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-600 mb-1">
                {overdueDeadlines.length} vencimiento(s) atrasado(s)
              </h3>
              <div className="space-y-2">
                {overdueDeadlines.slice(0, 3).map((deadline) => (
                  <div
                    key={deadline.id}
                    className="text-sm text-red-600 cursor-pointer hover:underline"
                    onClick={() => onDeadlineClick?.(deadline.id)}
                  >
                    {deadline.companyName} - {deadline.declarationType} (
                    {Math.abs(deadline.daysUntilDue)} días vencido)
                  </div>
                ))}
                {overdueDeadlines.length > 3 && (
                  <p className="text-sm text-red-600">
                    Y {overdueDeadlines.length - 3} más...
                  </p>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Calendar view */}
      {view === 'month' && (
        <Card className="p-4">
          {isLoading ? (
            <div className="animate-pulse space-y-4">
              <div className="h-10 bg-muted rounded" />
              <div className="grid grid-cols-7 gap-2">
                {[...Array(35)].map((_, i) => (
                  <div key={i} className="h-24 bg-muted rounded" />
                ))}
              </div>
            </div>
          ) : (
            <div>
              {/* Weekday headers */}
              <div className="grid grid-cols-7 gap-2 mb-2">
                {['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map((day) => (
                  <div
                    key={day}
                    className="text-center text-sm font-semibold text-muted-foreground py-2"
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* Calendar grid */}
              <div className="grid grid-cols-7 gap-2">
                {calendarDays.map((day) => {
                  const dateKey = format(day, 'yyyy-MM-dd')
                  const dayDeadlines = deadlinesByDate.get(dateKey) || []
                  const isCurrentMonth = isSameMonth(day, currentDate)
                  const isTodayDate = isToday(day)

                  return (
                    <div
                      key={day.toString()}
                      className={cn(
                        'min-h-[100px] p-2 border rounded-lg',
                        !isCurrentMonth && 'bg-muted/50 text-muted-foreground',
                        isTodayDate && 'border-primary border-2 bg-primary/5'
                      )}
                    >
                      <div
                        className={cn(
                          'text-sm font-medium mb-1',
                          isTodayDate && 'text-primary'
                        )}
                      >
                        {format(day, 'd')}
                      </div>

                      {/* Deadlines for this day */}
                      <div className="space-y-1">
                        {dayDeadlines.slice(0, 2).map((deadline) => (
                          <div
                            key={deadline.id}
                            className="text-xs p-1 rounded cursor-pointer hover:bg-muted transition-colors"
                            onClick={() => onDeadlineClick?.(deadline.id)}
                          >
                            <div className="flex items-center gap-1">
                              <div
                                className={cn(
                                  'w-2 h-2 rounded-full shrink-0',
                                  getPriorityColor(deadline.priority)
                                )}
                              />
                              <span className="truncate font-medium">
                                {deadline.companyName}
                              </span>
                            </div>
                            <div className="text-muted-foreground truncate">
                              {deadline.declarationType}
                            </div>
                          </div>
                        ))}
                        {dayDeadlines.length > 2 && (
                          <div className="text-xs text-muted-foreground px-1">
                            +{dayDeadlines.length - 2} más
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* List view */}
      {view === 'list' && (
        <Card className="p-4">
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-20 bg-muted rounded animate-pulse" />
              ))}
            </div>
          ) : deadlines && deadlines.length > 0 ? (
            <div className="space-y-3">
              {deadlines.map((deadline) => (
                <div
                  key={deadline.id}
                  className="flex items-center gap-4 p-4 border rounded-lg cursor-pointer hover:bg-muted transition-colors"
                  onClick={() => onDeadlineClick?.(deadline.id)}
                >
                  {/* Priority indicator */}
                  <div
                    className={cn(
                      'w-1 h-full rounded-full',
                      getPriorityColor(deadline.priority)
                    )}
                  />

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex-1 min-w-0">
                        <h4 className="font-semibold truncate">
                          {deadline.companyName}
                        </h4>
                        <p className="text-sm text-muted-foreground">
                          {deadline.declarationType}
                        </p>
                      </div>
                      <Badge className={getPriorityColor(deadline.priority)}>
                        {getPriorityLabel(deadline.priority)}
                      </Badge>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                      <div className="flex items-center gap-1">
                        <Calendar className="h-4 w-4" />
                        <span>{formatDate(deadline.dueDate)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Clock className="h-4 w-4" />
                        <span>
                          {deadline.daysUntilDue < 0
                            ? `${Math.abs(deadline.daysUntilDue)} días vencido`
                            : `${deadline.daysUntilDue} días restantes`}
                        </span>
                      </div>
                      {deadline.amount && (
                        <div className="flex items-center gap-1">
                          <TrendingUp className="h-4 w-4" />
                          <span className="font-medium">
                            {formatCurrency(deadline.amount)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <Calendar className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay vencimientos en este período</p>
            </div>
          )}
        </Card>
      )}

      {/* Legend */}
      <Card className="p-4">
        <h3 className="text-sm font-semibold mb-3">Prioridad</h3>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-sm">Urgente</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500" />
            <span className="text-sm">Alta</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="text-sm">Media</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-sm">Baja</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
