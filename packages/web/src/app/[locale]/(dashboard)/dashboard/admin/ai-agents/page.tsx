'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import {
  Bot, Cpu, RefreshCw, Zap, AlertTriangle,
  CheckCircle2, XCircle, Activity, DollarSign,
  BarChart3, Shield, Workflow, Hash,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useToast } from '@/hooks/use-toast'
import {
  aiAgentsApi,
  type AgentInfo,
  type TokenUsageStats,
} from '@/modules/companies/services/classification-api'

// ── Agent visual mapping (icon + color only — label comes from backend) ──────

const AGENT_VISUAL: Record<string, { icon: typeof Bot; color: string }> = {
  treasury_analyst: { icon: DollarSign, color: 'bg-emerald-100 text-emerald-800' },
  admin_assistant: { icon: Shield, color: 'bg-blue-100 text-blue-800' },
  supervisor_tools: { icon: Activity, color: 'bg-purple-100 text-purple-800' },
  orchestrator: { icon: Workflow, color: 'bg-indigo-100 text-indigo-800' },
  chatbot_rag: { icon: Bot, color: 'bg-cyan-100 text-cyan-800' },
  document_processor: { icon: Cpu, color: 'bg-orange-100 text-orange-800' },
  batch_classifier: { icon: Zap, color: 'bg-yellow-100 text-yellow-800' },
  enrichment: { icon: BarChart3, color: 'bg-pink-100 text-pink-800' },
  briefing: { icon: Activity, color: 'bg-teal-100 text-teal-800' },
  routing: { icon: Workflow, color: 'bg-violet-100 text-violet-800' },
  company_classifier: { icon: Bot, color: 'bg-green-100 text-green-800' },
}

function getAgentVisual(agentType: string) {
  return AGENT_VISUAL[agentType] || { icon: Bot, color: 'bg-gray-100 text-gray-800' }
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function AIAgentsPage() {
  const t = useTranslations('admin')
  const { toast } = useToast()

  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [agentsTotal, setAgentsTotal] = useState(0)
  const [tokenStats, setTokenStats] = useState<TokenUsageStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('registry')

  const fetchAgents = useCallback(async () => {
    setLoading(true)
    try {
      const res = await aiAgentsApi.listAgents()
      setAgents(res.agents)
      setAgentsTotal(res.total)
    } catch {
      toast({ title: 'Error', description: t('aiAgents.loadError'), variant: 'destructive' })
    } finally {
      setLoading(false)
    }
  }, [toast, t])

  const fetchTokenStats = useCallback(async () => {
    try {
      const res = await aiAgentsApi.getTokenUsage()
      setTokenStats(res)
    } catch {
      // Silent — non-critical
    }
  }, [])

  useEffect(() => {
    fetchAgents()
    fetchTokenStats()
  }, [fetchAgents, fetchTokenStats])

  useEffect(() => {
    if (activeTab === 'usage') fetchTokenStats()
  }, [activeTab, fetchTokenStats])

  const errorRate = tokenStats ? (tokenStats.totalRequests > 0
    ? ((tokenStats.failedRequests / tokenStats.totalRequests) * 100)
    : 0) : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Cpu className="h-6 w-6" />
            {t('aiAgents.title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t('aiAgents.subtitle')}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { fetchAgents(); fetchTokenStats() }}>
          <RefreshCw className="h-4 w-4 mr-2" />
          {t('aiAgents.refresh')}
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Bot className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{t('aiAgents.totalAgents')}</p>
            </div>
            <p className="text-2xl font-bold">{agentsTotal}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Hash className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{t('aiAgents.totalRequests')}</p>
            </div>
            <p className="text-2xl font-bold">{tokenStats?.totalRequests ?? '-'}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{t('aiAgents.totalTokens')}</p>
            </div>
            <p className="text-2xl font-bold">
              {tokenStats
                ? `${((tokenStats.totalTokensIn + tokenStats.totalTokensOut) / 1000).toFixed(1)}K`
                : '-'}
            </p>
            {tokenStats && (
              <p className="text-xs text-muted-foreground mt-1">
                In: {(tokenStats.totalTokensIn / 1000).toFixed(1)}K / Out: {(tokenStats.totalTokensOut / 1000).toFixed(1)}K
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-1">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">{t('aiAgents.estimatedCost')}</p>
            </div>
            <p className="text-2xl font-bold">
              ${tokenStats?.estimatedCostUsd?.toFixed(4) ?? '0.0000'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">{tokenStats?.model ?? 'gemini-2.0-flash'}</p>
          </CardContent>
        </Card>
      </div>

      {/* Circuit Breaker Alert */}
      {tokenStats?.circuitOpen && (
        <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0" />
          <div>
            <p className="font-medium text-red-800">{t('aiAgents.circuitBreakerOpen')}</p>
            <p className="text-sm text-red-600">
              {t('aiAgents.circuitBreakerDesc')}
            </p>
          </div>
        </div>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="registry" className="gap-1">
            <Bot className="h-4 w-4" />
            {t('aiAgents.registryTab')} ({agentsTotal})
          </TabsTrigger>
          <TabsTrigger value="usage" className="gap-1">
            <BarChart3 className="h-4 w-4" />
            {t('aiAgents.usageTab')}
          </TabsTrigger>
        </TabsList>

        {/* Registry Tab */}
        <TabsContent value="registry" className="space-y-4">
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('aiAgents.agentType')}</TableHead>
                    <TableHead>{t('aiAgents.pattern')}</TableHead>
                    <TableHead className="text-center">{t('aiAgents.functions')}</TableHead>
                    <TableHead className="text-center">{t('aiAgents.processFn')}</TableHead>
                    <TableHead>{t('aiAgents.subAgents')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {loading ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8">
                        <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2" />
                        {t('aiAgents.loading')}
                      </TableCell>
                    </TableRow>
                  ) : agents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                        {t('aiAgents.noAgents')}
                      </TableCell>
                    </TableRow>
                  ) : (
                    agents.map((agent) => {
                      const visual = getAgentVisual(agent.agentType)
                      const Icon = visual.icon
                      // Label comes from backend (ToolRegistry agent_type_label)
                      const displayLabel = agent.label || agent.agentType
                      const pattern = agent.hasFunctions && agent.hasProcessFn
                        ? 'Hybrid'
                        : agent.hasFunctions
                          ? 'Function-Calling'
                          : agent.hasProcessFn
                            ? 'Process Pipeline'
                            : 'Passive'

                      return (
                        <TableRow key={agent.agentType}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Badge className={`${visual.color} gap-1`}>
                                <Icon className="h-3 w-3" />
                                {displayLabel}
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground mt-1 font-mono">{agent.agentType}</p>
                          </TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">{pattern}</Badge>
                          </TableCell>
                          <TableCell className="text-center">
                            {agent.hasFunctions ? (
                              <span className="inline-flex items-center gap-1 text-green-600">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                {agent.functionCount}
                              </span>
                            ) : (
                              <XCircle className="h-3.5 w-3.5 text-muted-foreground mx-auto" />
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {agent.hasProcessFn ? (
                              <CheckCircle2 className="h-3.5 w-3.5 text-green-600 mx-auto" />
                            ) : (
                              <XCircle className="h-3.5 w-3.5 text-muted-foreground mx-auto" />
                            )}
                          </TableCell>
                          <TableCell>
                            {agent.subAgents.length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {agent.subAgents.map((sa) => (
                                  <Badge key={sa} variant="secondary" className="text-xs">{sa}</Badge>
                                ))}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Usage Tab */}
        <TabsContent value="usage" className="space-y-4">
          {!tokenStats ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                <Cpu className="h-8 w-8 mx-auto mb-2 opacity-50" />
                {t('aiAgents.noUsageData')}
              </CardContent>
            </Card>
          ) : (
            <>
              {/* SDK Status */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    {t('aiAgents.sdkStatus')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.sdkInitialized')}</p>
                      <div className="flex items-center gap-1 mt-1">
                        {tokenStats.sdkInitialized ? (
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-600" />
                        )}
                        <span className="text-sm font-medium">
                          {tokenStats.sdkInitialized ? t('aiAgents.active') : t('aiAgents.inactive')}
                        </span>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.gcpProject')}</p>
                      <p className="text-sm font-mono mt-1">{tokenStats.project || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.gcpLocation')}</p>
                      <p className="text-sm font-mono mt-1">{tokenStats.location || '-'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.model')}</p>
                      <p className="text-sm font-mono mt-1">{tokenStats.model}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Reliability */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    {t('aiAgents.reliability')}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.successRate')}</p>
                      <p className="text-lg font-bold text-green-600">
                        {tokenStats.totalRequests > 0
                          ? `${(100 - errorRate).toFixed(1)}%`
                          : '-'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.failedRequests')}</p>
                      <p className="text-lg font-bold text-red-600">{tokenStats.failedRequests}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.consecutiveFailures')}</p>
                      <p className={`text-lg font-bold ${tokenStats.consecutiveFailures > 5 ? 'text-red-600' : 'text-gray-900'}`}>
                        {tokenStats.consecutiveFailures}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t('aiAgents.circuitBreaker')}</p>
                      <Badge className={tokenStats.circuitOpen ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}>
                        {tokenStats.circuitOpen ? t('aiAgents.cbOpen') : t('aiAgents.cbClosed')}
                      </Badge>
                    </div>
                  </div>

                  {/* Error rate bar */}
                  <div>
                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                      <span>{t('aiAgents.errorRate')}</span>
                      <span>{errorRate.toFixed(1)}%</span>
                    </div>
                    <Progress
                      value={errorRate}
                      className={`h-2 ${errorRate > 10 ? '[&>div]:bg-red-500' : '[&>div]:bg-green-500'}`}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Token Breakdown */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Zap className="h-4 w-4" />
                    {t('aiAgents.tokenBreakdown')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                    <div className="p-4 bg-blue-50 rounded-lg">
                      <p className="text-xs text-blue-600 font-medium">{t('aiAgents.inputTokens')}</p>
                      <p className="text-xl font-bold text-blue-900">
                        {(tokenStats.totalTokensIn / 1000).toFixed(1)}K
                      </p>
                      <p className="text-xs text-blue-600 mt-1">
                        ${(tokenStats.totalTokensIn * 0.0000001).toFixed(4)} USD
                      </p>
                    </div>
                    <div className="p-4 bg-purple-50 rounded-lg">
                      <p className="text-xs text-purple-600 font-medium">{t('aiAgents.outputTokens')}</p>
                      <p className="text-xl font-bold text-purple-900">
                        {(tokenStats.totalTokensOut / 1000).toFixed(1)}K
                      </p>
                      <p className="text-xs text-purple-600 mt-1">
                        ${(tokenStats.totalTokensOut * 0.0000004).toFixed(4)} USD
                      </p>
                    </div>
                    <div className="p-4 bg-green-50 rounded-lg">
                      <p className="text-xs text-green-600 font-medium">{t('aiAgents.totalCost')}</p>
                      <p className="text-xl font-bold text-green-900">
                        ${tokenStats.estimatedCostUsd?.toFixed(4) ?? '0.0000'}
                      </p>
                      <p className="text-xs text-green-600 mt-1">Gemini 2.0 Flash</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
