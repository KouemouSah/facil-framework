'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings,
  Server,
  Database,
  Mail,
  Shield,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
  AlertCircle,
  Play,
  Info,
} from 'lucide-react'
import { fetchClient } from '@/core/api'
import { toast } from 'sonner'

// Types
interface SecretsStatus {
  [key: string]: boolean
}

interface SmtpConfiguration {
  smtp_host: string
  smtp_port: number
  smtp_username: string
  smtp_from_email: string
  smtp_from_name: string
  smtp_use_tls: boolean
  smtp_password_configured: boolean
  smtp_password_length: number
}

interface DiagnosticResponse {
  success: boolean
  secrets_status: SecretsStatus
  smtp_configuration: SmtpConfiguration
  message: string
}

interface MigrationResponse {
  success: boolean
  migration: string
  users_grandfathered: number
  message: string
}

// API functions
const adminApi = {
  checkSecrets: async (): Promise<DiagnosticResponse> => {
    return fetchClient.get<DiagnosticResponse>('/admin/diagnostic/secrets')
  },
  runGrandfatherMigration: async (): Promise<MigrationResponse> => {
    return fetchClient.post<MigrationResponse>('/admin/migrate/grandfather-users')
  },
  healthCheck: async (): Promise<{ status: string; timestamp: string }> => {
    return fetchClient.get('/admin/health')
  },
}

export default function SettingsPage() {
  const t = useTranslations('admin.settings')
  const tCommon = useTranslations('common')
  const queryClient = useQueryClient()

  // State - reserved for future migration dialog
  const [_isMigrationDialogOpen, _setIsMigrationDialogOpen] = useState(false)

  // Queries
  const {
    data: diagnosticsData,
    isLoading: isLoadingDiagnostics,
    error: diagnosticsError,
    refetch: refetchDiagnostics,
  } = useQuery({
    queryKey: ['admin', 'diagnostics'],
    queryFn: adminApi.checkSecrets,
    retry: false,
  })

  // Mutations
  const migrationMutation = useMutation({
    mutationFn: adminApi.runGrandfatherMigration,
    onSuccess: (data) => {
      toast.success(data.message || 'Migration completed successfully')
      queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Migration failed')
    },
  })

  // Status check helper
  const getStatusBadge = (isOk: boolean) => {
    if (isOk) {
      return (
        <Badge className="bg-green-100 text-green-800 gap-1">
          <CheckCircle2 className="h-3 w-3" />
          OK
        </Badge>
      )
    }
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" />
        Error
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('title') || 'Settings'}</h1>
          <p className="text-muted-foreground">{t('subtitle') || 'System configuration and diagnostics'}</p>
        </div>
        <Button variant="outline" onClick={() => refetchDiagnostics()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {tCommon('refresh') || 'Refresh'}
        </Button>
      </div>

      {/* System Status Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('systemStatus') || 'System Status'}</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {t('operational') || 'Operational'}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {t('allServicesRunning') || 'All services running'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('database') || 'Database'}</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">Supabase</div>
            <p className="text-xs text-muted-foreground mt-1">
              PostgreSQL 15+
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t('authentication') || 'Authentication'}</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">JWT + 2FA</div>
            <p className="text-xs text-muted-foreground mt-1">
              TOTP-based authentication
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Diagnostics Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            {t('diagnostics') || 'System Diagnostics'}
          </CardTitle>
          <CardDescription>
            {t('diagnosticsDescription') || 'Check system configuration and services status'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingDiagnostics ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : diagnosticsError ? (
            <div className="flex items-center gap-2 text-destructive py-4">
              <AlertCircle className="h-5 w-5" />
              <span>
                {diagnosticsError instanceof Error
                  ? diagnosticsError.message
                  : 'Failed to load diagnostics'}
              </span>
              <Button variant="outline" size="sm" onClick={() => refetchDiagnostics()} className="ml-auto">
                {tCommon('retry') || 'Retry'}
              </Button>
            </div>
          ) : diagnosticsData ? (
            <div className="space-y-6">
              {/* Secrets Status */}
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  {t('secretsConfiguration') || 'Secrets Configuration'}
                </h3>
                <div className="grid gap-2">
                  {Object.entries(diagnosticsData.secrets_status || {}).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between py-2 px-3 bg-muted/50 rounded-lg">
                      <span className="text-sm font-mono">{key}</span>
                      {getStatusBadge(value)}
                    </div>
                  ))}
                </div>
              </div>

              <Separator />

              {/* SMTP Configuration */}
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Mail className="h-4 w-4" />
                  {t('emailConfiguration') || 'Email Configuration'}
                </h3>
                {diagnosticsData.smtp_configuration && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-4 p-4 bg-muted/50 rounded-lg">
                      <div>
                        <p className="text-xs text-muted-foreground">SMTP Host</p>
                        <p className="text-sm font-medium">{diagnosticsData.smtp_configuration.smtp_host || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">SMTP Port</p>
                        <p className="text-sm font-medium">{diagnosticsData.smtp_configuration.smtp_port || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">From Email</p>
                        <p className="text-sm font-medium">{diagnosticsData.smtp_configuration.smtp_from_email || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">From Name</p>
                        <p className="text-sm font-medium">{diagnosticsData.smtp_configuration.smtp_from_name || '-'}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">TLS Enabled</p>
                        <p className="text-sm font-medium">
                          {diagnosticsData.smtp_configuration.smtp_use_tls ? 'Yes' : 'No'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Password Configured</p>
                        {getStatusBadge(diagnosticsData.smtp_configuration.smtp_password_configured)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Maintenance Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Play className="h-5 w-5" />
            {t('maintenanceActions') || 'Maintenance Actions'}
          </CardTitle>
          <CardDescription>
            {t('maintenanceDescription') || 'Database migrations and maintenance tasks'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Grandfather Migration */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <h4 className="text-sm font-medium">{t('grandfatherMigration') || 'Grandfather Users Migration'}</h4>
                </div>
                <p className="text-sm text-muted-foreground">
                  {t('grandfatherMigrationDescription') ||
                    'Set email_verified=TRUE for users created before Nov 3, 2025'}
                </p>
              </div>
              <Button
                variant="outline"
                onClick={() => migrationMutation.mutate()}
                disabled={migrationMutation.isPending}
              >
                {migrationMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Play className="mr-2 h-4 w-4" />
                )}
                {t('runMigration') || 'Run Migration'}
              </Button>
            </div>

            {/* Info Banner */}
            <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <Info className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-900">
                  {t('deploymentNote') || 'Deployment Note'}
                </p>
                <p className="text-sm text-blue-700">
                  {t('deploymentNoteDescription') ||
                    'Deployments are handled automatically via GitHub Actions. Never run manual cloud builds.'}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* System Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            {t('systemInfo') || 'System Information'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-muted/50 rounded-lg">
              <p className="text-xs text-muted-foreground">Platform</p>
              <p className="text-sm font-medium">Facil</p>
            </div>
            <div className="p-3 bg-muted/50 rounded-lg">
              <p className="text-xs text-muted-foreground">Backend</p>
              <p className="text-sm font-medium">FastAPI + Python 3.11</p>
            </div>
            <div className="p-3 bg-muted/50 rounded-lg">
              <p className="text-xs text-muted-foreground">Frontend</p>
              <p className="text-sm font-medium">Next.js 14</p>
            </div>
            <div className="p-3 bg-muted/50 rounded-lg">
              <p className="text-xs text-muted-foreground">Deployment</p>
              <p className="text-sm font-medium">Cloud Run + Firebase</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
