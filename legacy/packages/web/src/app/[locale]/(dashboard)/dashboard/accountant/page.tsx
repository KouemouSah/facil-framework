'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useTranslations } from 'next-intl'
import {
  ClientList,
  DeadlineCalendar,
  ClientSwitcher,
  TaskQueue,
  useDashboardSummary,
  useHighPriorityTasks,
  useOverdueDeadlines,
} from '@/modules/accountant'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Users,
  FileText,
  Calendar,
  AlertCircle,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react'
import { formatCurrency } from '@/core/utils'

/**
 * Accountant Multi-Client Dashboard Page
 *
 * Provides a comprehensive view of all client companies managed by the accountant.
 * Features:
 * - Dashboard summary with key metrics
 * - Client list with quick stats
 * - Deadline calendar
 * - Task queue with priorities
 * - Quick client switcher
 *
 * @page /dashboard/accountant
 */
export default function AccountantDashboardPage() {
  const router = useRouter()
  const t = useTranslations('accountant')
  const [selectedClient, setSelectedClient] = useState<string>()
  const [activeTab, setActiveTab] = useState('overview')

  // Fetch dashboard data
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary()
  const { data: highPriorityTasks } = useHighPriorityTasks()
  const { data: overdueDeadlines } = useOverdueDeadlines()

  const handleClientSelect = (companyId: string) => {
    setSelectedClient(companyId)
    setActiveTab('client-detail')
  }

  const handleDeadlineClick = (declarationId: string) => {
    router.push(`/dashboard/declarations/${declarationId}`)
  }

  const handleTaskClick = (declarationId: string) => {
    router.push(`/dashboard/declarations/${declarationId}`)
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('title')}</h1>
          <p className="text-muted-foreground">
            {t('subtitle')}
          </p>
        </div>

        {/* Client Switcher */}
        <div className="w-full md:w-[400px]">
          <ClientSwitcher
            value={selectedClient}
            onValueChange={setSelectedClient}
            placeholder={t('selectClient')}
          />
        </div>
      </div>

      {/* Alerts Section */}
      {(overdueDeadlines && overdueDeadlines.length > 0) ||
      (highPriorityTasks && highPriorityTasks.length > 0) ? (
        <div className="space-y-3">
          {/* Overdue Deadlines Alert */}
          {overdueDeadlines && overdueDeadlines.length > 0 && (
            <Card className="p-4 border-red-500 bg-red-50 dark:bg-red-950/20">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <h3 className="font-semibold text-red-600 mb-1">
                    {t('overdueCount', { count: overdueDeadlines.length })}
                  </h3>
                  <p className="text-sm text-red-600">
                    {t('overdueDescription')}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveTab('deadlines')}
                  className="border-red-500 text-red-600 hover:bg-red-100"
                >
                  {t('viewDetails')}
                </Button>
              </div>
            </Card>
          )}

          {/* High Priority Tasks Alert */}
          {highPriorityTasks && highPriorityTasks.length > 0 && (
            <Card className="p-4 border-orange-500 bg-orange-50 dark:bg-orange-950/20">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-orange-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <h3 className="font-semibold text-orange-600 mb-1">
                    {t('highPriorityCount', { count: highPriorityTasks.length })}
                  </h3>
                  <p className="text-sm text-orange-600">
                    {t('highPriorityDescription')}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setActiveTab('tasks')}
                  className="border-orange-500 text-orange-600 hover:bg-orange-100"
                >
                  {t('viewTasks')}
                </Button>
              </div>
            </Card>
          )}
        </div>
      ) : null}

      {/* Summary Stats Cards */}
      {summaryLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="space-y-3">
                <div className="h-4 bg-muted rounded w-2/3" />
                <div className="h-8 bg-muted rounded w-1/2" />
                <div className="h-3 bg-muted rounded w-full" />
              </div>
            </Card>
          ))}
        </div>
      ) : summary ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Total Clients */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('stats.totalClients')}</p>
                <p className="text-3xl font-bold">{summary.totalClients}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {t('stats.activeCount', { count: summary.activeClients })}
                </p>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-950/20 rounded-lg">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
            </div>
          </Card>

          {/* Pending Declarations */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('stats.declarations')}</p>
                <p className="text-3xl font-bold">
                  {summary.totalPendingDeclarations}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  {t('stats.inReviewCount', { count: summary.totalInReviewDeclarations })}
                </p>
              </div>
              <div className="p-3 bg-orange-100 dark:bg-orange-950/20 rounded-lg">
                <FileText className="h-6 w-6 text-orange-600" />
              </div>
            </div>
          </Card>

          {/* Upcoming Deadlines */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('stats.deadlines')}</p>
                <p className="text-3xl font-bold">{summary.upcomingDeadlines}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {t('stats.dueThisWeek', { count: summary.dueThisWeekCount })}
                </p>
              </div>
              <div className="p-3 bg-purple-100 dark:bg-purple-950/20 rounded-lg">
                <Calendar className="h-6 w-6 text-purple-600" />
              </div>
            </div>
          </Card>

          {/* Total Amount Due */}
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{t('stats.totalAmount')}</p>
                <p className="text-3xl font-bold">
                  {formatCurrency(summary.totalAmountDue)}
                </p>
                <p className="text-xs text-red-600 mt-1">
                  {t('stats.overdueAmount', { amount: formatCurrency(summary.totalOverdueAmount) })}
                </p>
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-950/20 rounded-lg">
                <TrendingUp className="h-6 w-6 text-green-600" />
              </div>
            </div>
          </Card>
        </div>
      ) : null}

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">{t('tabs.overview')}</TabsTrigger>
          <TabsTrigger value="clients">{t('tabs.clients')}</TabsTrigger>
          <TabsTrigger value="deadlines">{t('tabs.deadlines')}</TabsTrigger>
          <TabsTrigger value="tasks">{t('tabs.tasks')}</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* High Priority Tasks */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">{t('priorityTasks')}</h3>
                <Badge variant="destructive">
                  {t('urgentCount', { count: summary?.urgentCount || 0 })}
                </Badge>
              </div>
              <TaskQueue
                initialFilters={{ priority: 'high', sortBy: 'dueDate' }}
                showFilters={false}
                onTaskClick={handleTaskClick}
              />
            </Card>

            {/* Recent Clients Activity */}
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">{t('recentClients')}</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setActiveTab('clients')}
                >
                  {t('viewAll')}
                </Button>
              </div>
              <ClientList
                initialFilters={{ sortBy: 'lastActivity' }}
                showSearch={false}
                showFilters={false}
                onClientSelect={handleClientSelect}
              />
            </Card>
          </div>

          {/* Upcoming Deadlines */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">{t('upcomingDeadlines')}</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setActiveTab('deadlines')}
              >
                {t('viewCalendar')}
              </Button>
            </div>
            <DeadlineCalendar
              companyId={selectedClient}
              onDeadlineClick={handleDeadlineClick}
            />
          </Card>
        </TabsContent>

        {/* Clients Tab */}
        <TabsContent value="clients" className="space-y-6">
          <ClientList
            onClientSelect={handleClientSelect}
            showSearch={true}
            showFilters={true}
          />
        </TabsContent>

        {/* Deadlines Tab */}
        <TabsContent value="deadlines" className="space-y-6">
          <DeadlineCalendar
            companyId={selectedClient}
            onDeadlineClick={handleDeadlineClick}
          />
        </TabsContent>

        {/* Tasks Tab */}
        <TabsContent value="tasks" className="space-y-6">
          <TaskQueue onTaskClick={handleTaskClick} showFilters={true} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
