/**
 * Accountant Module - Usage Examples
 *
 * This file demonstrates various ways to use the accountant module components and hooks.
 * Copy these examples into your pages/components as needed.
 *
 * @module accountant/examples
 * @author Claude Code
 * @date 2025-12-03
 */

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  // Components
  ClientList,
  DeadlineCalendar,
  ClientSwitcher,
  TaskQueue,
  // Hooks
  useAccountantClients,
  useClientStats,
  useUpcomingDeadlines,
  useOverdueDeadlines,
  useClientDeadlines,
  usePendingTasks,
  useHighPriorityTasks,
  useTasksRequiringAction,
  useDashboardSummary,
  useInvalidateAccountantQueries,
  usePrefetchClient,
  // Types
  type ClientFilters,
} from '@/modules/accountant'

// =============================================================================
// EXAMPLE 1: Basic Dashboard Layout
// =============================================================================

export function Example1_BasicDashboard() {
  const router = useRouter()
  const [selectedClient, setSelectedClient] = useState<string>()

  return (
    <div className="space-y-6">
      {/* Header with client switcher */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Panel de Contador</h1>
        <ClientSwitcher
          value={selectedClient}
          onValueChange={setSelectedClient}
        />
      </div>

      {/* Client list */}
      <ClientList onClientSelect={setSelectedClient} />

      {/* Deadline calendar */}
      <DeadlineCalendar
        companyId={selectedClient}
        onDeadlineClick={(id) => router.push(`/declarations/${id}`)}
      />

      {/* Task queue */}
      <TaskQueue onTaskClick={(id) => router.push(`/declarations/${id}`)} />
    </div>
  )
}

// =============================================================================
// EXAMPLE 2: Dashboard with Summary Stats
// =============================================================================

export function Example2_DashboardWithStats() {
  const { data: summary, isLoading } = useDashboardSummary()

  if (isLoading) {
    return <div>Loading...</div>
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="p-6 border rounded-lg">
          <h3 className="text-sm text-muted-foreground">Clientes Totales</h3>
          <p className="text-3xl font-bold">{summary?.totalClients}</p>
          <p className="text-xs text-muted-foreground">
            {summary?.activeClients} activos
          </p>
        </div>

        <div className="p-6 border rounded-lg">
          <h3 className="text-sm text-muted-foreground">Pendientes</h3>
          <p className="text-3xl font-bold">
            {summary?.totalPendingDeclarations}
          </p>
          <p className="text-xs text-muted-foreground">
            {summary?.totalInReviewDeclarations} en revisión
          </p>
        </div>

        <div className="p-6 border rounded-lg">
          <h3 className="text-sm text-muted-foreground">Vencimientos</h3>
          <p className="text-3xl font-bold">{summary?.upcomingDeadlines}</p>
          <p className="text-xs text-red-600">
            {summary?.overdueDeadlines} vencidos
          </p>
        </div>

        <div className="p-6 border rounded-lg">
          <h3 className="text-sm text-muted-foreground">Tareas Urgentes</h3>
          <p className="text-3xl font-bold">{summary?.urgentCount}</p>
          <p className="text-xs text-muted-foreground">
            {summary?.requiresActionCount} requieren acción
          </p>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// EXAMPLE 3: Filtered Client List
// =============================================================================

export function Example3_FilteredClientList() {
  const [filters, setFilters] = useState<ClientFilters>({
    status: 'active',
    hasPendingDeclarations: true,
    sortBy: 'pendingCount',
    sortOrder: 'desc',
  })

  const { data: _data, isLoading: _isLoading } = useAccountantClients(filters)

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">Clientes con Pendientes</h2>

      {/* Custom filter controls */}
      <div className="flex gap-2">
        <button
          onClick={() => setFilters({ ...filters, status: 'active' })}
          className="px-4 py-2 border rounded"
        >
          Activos
        </button>
        <button
          onClick={() => setFilters({ ...filters, hasOverduePayments: true })}
          className="px-4 py-2 border rounded"
        >
          Con pagos vencidos
        </button>
      </div>

      {/* Client list */}
      <ClientList initialFilters={filters} />
    </div>
  )
}

// =============================================================================
// EXAMPLE 4: Task Queue with Priority Filter
// =============================================================================

export function Example4_PriorityTaskQueue() {
  const { data: urgentTasks } = usePendingTasks({
    priority: 'urgent',
    sortBy: 'dueDate',
  })

  const { data: highPriorityTasks } = useHighPriorityTasks()
  const { data: actionRequired } = useTasksRequiringAction()

  return (
    <div className="space-y-6">
      {/* Urgent Tasks */}
      <section>
        <h2 className="text-xl font-bold mb-4">
          Tareas Urgentes ({urgentTasks?.length || 0})
        </h2>
        <TaskQueue
          initialFilters={{ priority: 'urgent', sortBy: 'dueDate' }}
          showFilters={false}
        />
      </section>

      {/* High Priority */}
      <section>
        <h2 className="text-xl font-bold mb-4">
          Alta Prioridad ({highPriorityTasks?.length || 0})
        </h2>
        <TaskQueue
          initialFilters={{ priority: 'high', sortBy: 'dueDate' }}
          showFilters={false}
        />
      </section>

      {/* Action Required */}
      <section>
        <h2 className="text-xl font-bold mb-4">
          Requieren Acción ({actionRequired?.length || 0})
        </h2>
        <div className="space-y-2">
          {actionRequired?.map((task) => (
            <div key={task.id} className="p-4 border rounded">
              <h3 className="font-semibold">{task.declarationType}</h3>
              <p className="text-sm text-muted-foreground">
                {task.companyName} - {task.actionType}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

// =============================================================================
// EXAMPLE 5: Client Detail View
// =============================================================================

export function Example5_ClientDetailView({ companyId }: { companyId: string }) {
  const { data: stats, isLoading } = useClientStats(companyId)
  const { data: _deadlines } = useClientDeadlines(companyId)

  if (isLoading) {
    return <div>Loading client details...</div>
  }

  return (
    <div className="space-y-6">
      {/* Client Header */}
      <div>
        <h1 className="text-3xl font-bold">{stats?.companyName}</h1>
        <p className="text-muted-foreground">NIF: {stats?.taxId}</p>
      </div>

      {/* Client Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="p-4 border rounded">
          <p className="text-sm text-muted-foreground">Pendientes</p>
          <p className="text-2xl font-bold">{stats?.pendingDeclarations}</p>
        </div>
        <div className="p-4 border rounded">
          <p className="text-sm text-muted-foreground">Borradores</p>
          <p className="text-2xl font-bold">{stats?.draftDeclarations}</p>
        </div>
        <div className="p-4 border rounded">
          <p className="text-sm text-muted-foreground">En Revisión</p>
          <p className="text-2xl font-bold">{stats?.inReviewDeclarations}</p>
        </div>
        <div className="p-4 border rounded">
          <p className="text-sm text-muted-foreground">Aprobados (mes)</p>
          <p className="text-2xl font-bold">{stats?.approvedThisMonth}</p>
        </div>
      </div>

      {/* Client Deadlines */}
      <DeadlineCalendar companyId={companyId} />
    </div>
  )
}

// =============================================================================
// EXAMPLE 6: Deadline Calendar with Filters
// =============================================================================

export function Example6_DeadlineCalendarFiltered() {
  const [companyId, setCompanyId] = useState<string>()

  const { data: _deadlines } = useUpcomingDeadlines({
    companyId,
    startDate: '2025-12-01',
    endDate: '2025-12-31',
  })

  const { data: overdueDeadlines } = useOverdueDeadlines()

  return (
    <div className="space-y-6">
      {/* Overdue Alert */}
      {overdueDeadlines && overdueDeadlines.length > 0 && (
        <div className="p-4 bg-red-50 border-red-500 rounded">
          <h3 className="font-semibold text-red-600">
            {overdueDeadlines.length} vencimientos atrasados
          </h3>
        </div>
      )}

      {/* Company Filter */}
      <ClientSwitcher value={companyId} onValueChange={setCompanyId} />

      {/* Calendar */}
      <DeadlineCalendar companyId={companyId} />
    </div>
  )
}

// =============================================================================
// EXAMPLE 7: Using Hooks Directly
// =============================================================================

export function Example7_DirectHookUsage() {
  const { data: clients, isLoading, error } = useAccountantClients()
  const { data: _tasks } = usePendingTasks()
  const invalidateQueries = useInvalidateAccountantQueries()
  const prefetchClient = usePrefetchClient()

  const handleRefresh = () => {
    invalidateQueries()
  }

  const handleClientHover = (companyId: string) => {
    // Prefetch client data for instant navigation
    prefetchClient(companyId)
  }

  if (isLoading) return <div>Loading...</div>
  if (error) return <div>Error loading data</div>

  return (
    <div>
      <button onClick={handleRefresh}>Refresh All Data</button>

      <div className="space-y-2">
        {clients?.clients.map((client) => (
          <div
            key={client.id}
            onMouseEnter={() => handleClientHover(client.id)}
            className="p-4 border rounded"
          >
            <h3>{client.legal_name}</h3>
            <p>Pending: {client.stats.pendingDeclarations}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// EXAMPLE 8: Optimistic Updates
// =============================================================================

export function Example8_OptimisticUpdates() {
  const invalidateQueries = useInvalidateAccountantQueries()

  const _handleDeclarationApproved = async (_declarationId: string) => {
    // Make API call to approve declaration
    // await approveDeclaration(_declarationId)

    // Invalidate all accountant queries to refetch fresh data
    invalidateQueries()
  }

  return (
    <TaskQueue
      onTaskClick={(id) => {
        // Handle task click
        console.log('Task clicked:', id)
      }}
    />
  )
}

// =============================================================================
// EXAMPLE 9: Custom Stats Display
// =============================================================================

export function Example9_CustomStatsDisplay() {
  const { data: summary } = useDashboardSummary()
  const { data: clients } = useAccountantClients({ status: 'active' })

  const avgPendingPerClient = summary
    ? summary.totalPendingDeclarations / summary.totalClients
    : 0

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="p-6 border rounded">
        <h3 className="text-sm text-muted-foreground">
          Promedio por Cliente
        </h3>
        <p className="text-2xl font-bold">{avgPendingPerClient.toFixed(1)}</p>
        <p className="text-xs text-muted-foreground">
          declaraciones pendientes
        </p>
      </div>

      <div className="p-6 border rounded">
        <h3 className="text-sm text-muted-foreground">Tasa de Aprobación</h3>
        <p className="text-2xl font-bold">
          {summary
            ? (
                (summary.totalApprovedThisMonth /
                  (summary.totalPendingDeclarations +
                    summary.totalApprovedThisMonth)) *
                100
              ).toFixed(1)
            : 0}
          %
        </p>
        <p className="text-xs text-muted-foreground">este mes</p>
      </div>

      <div className="p-6 border rounded">
        <h3 className="text-sm text-muted-foreground">Clientes con Vencidos</h3>
        <p className="text-2xl font-bold">
          {clients?.clients.filter((c) => c.stats.overdueAmount > 0).length || 0}
        </p>
        <p className="text-xs text-muted-foreground">
          de {clients?.total || 0} totales
        </p>
      </div>
    </div>
  )
}

// =============================================================================
// EXAMPLE 10: Responsive Layout
// =============================================================================

export function Example10_ResponsiveLayout() {
  const [view, setView] = useState<'grid' | 'list'>('grid')

  return (
    <div className="space-y-4">
      {/* View Toggle */}
      <div className="flex gap-2">
        <button onClick={() => setView('grid')}>Grid View</button>
        <button onClick={() => setView('list')}>List View</button>
      </div>

      {/* Conditional Rendering */}
      {view === 'grid' ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <ClientList showSearch={true} showFilters={true} />
        </div>
      ) : (
        <div className="max-w-4xl mx-auto">
          <ClientList showSearch={true} showFilters={true} />
        </div>
      )}
    </div>
  )
}
