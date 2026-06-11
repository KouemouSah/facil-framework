'use client'

/**
 * Funcionario Dashboard Page
 * Dashboard for verified civil servants to access civil servant-specific services
 * Displays FUNCION_PUBLICA workflows directly as cards (no category grouping)
 */

import { useEffect, useState, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import {
  BadgeCheck,
  FileText,
  Shield,
  AlertCircle,
  Search,
  Loader2,
  User,
  Calendar,
  CreditCard,
  ChevronRight,
  Building,
} from 'lucide-react'
import { getAuthData } from '@/core/auth/storage'
import { useServiceRequests, wizardSessionApi } from '@/modules/service-requests'
import type { WorkflowConfig } from '@/modules/service-requests'
import type { User as UserType } from '@/types/auth'
import { FEATURE_CACHE_FIRST_WIZARD } from '@/core/config/features'
import { useWorkflowTranslations, workflowNameKey } from '@/hooks/use-workflow-translations'

// Sub-type labels moved to SELECTION steps in each workflow definition.
// The wizard SELECTION step renders options with labels and descriptions from backend config.

export default function FuncionarioDashboardPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('funcionarioDashboard')
  const tService = useTranslations('service_requests')

  // User state
  const [user, setUser] = useState<UserType | null>(null)
  const [isLoadingUser, setIsLoadingUser] = useState(true)

  // Workflows state
  const [workflows, setWorkflows] = useState<WorkflowConfig[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [isStarting, setIsStarting] = useState(false)

  const { loadWorkflows, startWorkflow, isLoading, error, clearError } = useServiceRequests()
  const { tw } = useWorkflowTranslations()

  // Check auth and load user
  useEffect(() => {
    const authData = getAuthData()

    if (!authData) {
      router.push(`/${locale}/auth`)
      return
    }

    setUser(authData.user)
    setIsLoadingUser(false)

    // Redirect if not a verified funcionario
    if (!authData.user.matricula_funcionario || !authData.user.funcionario_verified_at) {
      router.push(`/${locale}/dashboard/profile`)
    }
  }, [router, locale])

  // Load workflows on mount
  useEffect(() => {
    if (isLoadingUser || !user) return

    const loadData = async () => {
      const data = await loadWorkflows()
      // Filter only FUNCION_PUBLICA workflows
      const fpWorkflows = data.filter((w: WorkflowConfig) => w.category === 'FUNCION_PUBLICA')
      setWorkflows(fpWorkflows)
    }
    loadData()
  }, [loadWorkflows, isLoadingUser, user])

  // Filter workflows by search
  const filteredWorkflows = useMemo(() => {
    if (!searchQuery.trim()) return workflows
    const query = searchQuery.toLowerCase()
    return workflows.filter(
      (w) =>
        w.workflowCode.toLowerCase().includes(query) ||
        w.serviceNameEs.toLowerCase().includes(query) ||
        w.entityCode.toLowerCase().includes(query)
    )
  }, [workflows, searchQuery])

  // Handle workflow selection — start wizard directly, SELECTION step handles sub_type
  const handleWorkflowSelect = (workflow: WorkflowConfig) => {
    startNewRequest(workflow.workflowCode)
  }

  // Start new request
  const startNewRequest = async (workflowCode: string) => {
    setIsStarting(true)
    try {
      // Cache-first wizard: create session in Redis, no DB writes
      if (FEATURE_CACHE_FIRST_WIZARD) {
        const session = await wizardSessionApi.createSession({
          workflow_code: workflowCode,
          solicitud_type: 'expedicion',
        })
        if (session) {
          router.push(`/${locale}/dashboard/service-requests/wizard/session/${session.sessionId}`)
        }
        return
      }

      // Legacy flow: create DB record, then redirect
      const request = await startWorkflow({
        workflowCode,
      })

      if (request) {
        router.push(`/${locale}/dashboard/service-requests/${request.id}/wizard`)
      }
    } catch (err) {
      console.error('Failed to start workflow:', err)
    } finally {
      setIsStarting(false)
    }
  }

  // Get workflow features icons
  const getWorkflowFeatures = (workflow: WorkflowConfig) => {
    const features: { icon: React.ElementType; label: string }[] = []

    if (workflow.requiresAgentReview) {
      features.push({
        icon: User,
        label: locale === 'es' ? 'Revision de agente' : locale === 'fr' ? 'Revision agent' : 'Agent review',
      })
    }
    if (workflow.requiresAppointment) {
      features.push({
        icon: Calendar,
        label: locale === 'es' ? 'Requiere cita' : locale === 'fr' ? 'Rendez-vous requis' : 'Appointment required',
      })
    }
    if (workflow.requiresNotaIngreso) {
      features.push({
        icon: CreditCard,
        label: locale === 'es' ? 'Nota de ingreso' : locale === 'fr' ? 'Note de versement' : 'Payment note',
      })
    }

    return features
  }

  // Loading state
  if (isLoadingUser || !user) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-muted-foreground">{t('loading')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight md:text-4xl flex items-center gap-2">
            <BadgeCheck className="h-8 w-8 text-primary" />
            {t('pageTitle')}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t('pageSubtitle')}
          </p>
        </div>
        <Badge className="bg-green-500">
          <BadgeCheck className="mr-1 h-3 w-3" />
          {t('verified')}
        </Badge>
      </div>

      {/* User Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            {t('infoTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">{t('fullName')}</p>
              <p className="font-medium">{user.full_name || `${user.first_name} ${user.last_name}`}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('matricula')}</p>
              <p className="font-medium">{user.matricula_funcionario}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('verifiedSince')}</p>
              <p className="font-medium">
                {user.funcionario_verified_at
                  ? new Date(user.funcionario_verified_at).toLocaleDateString(locale)
                  : '-'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {typeof error === 'string' ? error : 'Une erreur est survenue'}
            <Button variant="link" size="sm" onClick={clearError} className="ml-2">
              {tService('close')}
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* Services Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold">{t('servicesTitle')}</h2>
          {workflows.length > 3 && (
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                placeholder={tService('search_placeholder') || 'Buscar...'}
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          )}
        </div>

        {/* Loading Workflows */}
        {isLoading && workflows.length === 0 && (
          <div className="flex items-center justify-center min-h-[200px]">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-primary" />
              <p className="text-muted-foreground">{tService('loading')}</p>
            </div>
          </div>
        )}

        {/* Workflows Grid - Direct display as cards */}
        {workflows.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredWorkflows.length === 0 ? (
              <div className="col-span-full text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium mb-2">
                  {locale === 'es'
                    ? 'No se encontraron tramites'
                    : locale === 'fr'
                      ? 'Aucune demarche trouvee'
                      : 'No services found'}
                </p>
                <p className="text-sm">
                  {locale === 'es'
                    ? 'Intenta con otros terminos de busqueda'
                    : locale === 'fr'
                      ? "Essayez avec d'autres termes de recherche"
                      : 'Try different search terms'}
                </p>
              </div>
            ) : (
              filteredWorkflows.map((workflow) => {
                const features = getWorkflowFeatures(workflow)

                return (
                  <Card
                    key={workflow.workflowCode}
                    className="cursor-pointer hover:border-primary hover:shadow-md transition-all group"
                    onClick={() => handleWorkflowSelect(workflow)}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between">
                        <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                          <FileText className="h-6 w-6" />
                        </div>
                        <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                      </div>
                      <CardTitle className="text-lg mt-3">{tw(workflowNameKey(workflow.workflowCode), workflow.serviceNameEs)}</CardTitle>
                      <CardDescription>{workflow.entityCode}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {features.length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {features.map((feature, idx) => {
                            const FeatureIcon = feature.icon
                            return (
                              <Badge key={idx} variant="outline" className="text-xs">
                                <FeatureIcon className="h-3 w-3 mr-1" />
                                {feature.label}
                              </Badge>
                            )
                          })}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })
            )}
          </div>
        )}

        {/* No workflows available */}
        {!isLoading && workflows.length === 0 && (
          <div className="text-center py-12">
            <Building className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <p className="text-lg font-medium mb-2">
              {locale === 'es'
                ? 'No hay tramites disponibles'
                : locale === 'fr'
                  ? 'Aucune demarche disponible'
                  : 'No services available'}
            </p>
            <p className="text-muted-foreground">
              {locale === 'es'
                ? 'Los tramites de funcionario estaran disponibles pronto'
                : locale === 'fr'
                  ? 'Les demarches fonctionnaire seront disponibles bientot'
                  : 'Civil servant services will be available soon'}
            </p>
          </div>
        )}
      </div>

      {/* Help Section */}
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>{t('helpTitle')}</AlertTitle>
        <AlertDescription>{t('helpDescription')}</AlertDescription>
      </Alert>

      {/* Starting Loading Overlay */}
      {isStarting && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-lg font-medium">
              {locale === 'es'
                ? 'Iniciando tu solicitud...'
                : locale === 'fr'
                  ? 'Demarrage de votre demande...'
                  : 'Starting your request...'}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
