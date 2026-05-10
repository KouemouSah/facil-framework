/**
 * EmailProviderSettings Component
 * Configuration page for Email providers (Gmail SMTP + SendGrid)
 * Shows current Gmail SMTP config (read-only) and allows adding SendGrid as alternative
 */

'use client'

import { useState } from 'react'
import {
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  Play,
  Loader2,
  Mail,
  Shield,
  Info,
  Lock,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  useProviderSettingsList,
  useCreateProviderSettings,
  useUpdateProviderSettings,
  useDeleteProviderSettings,
  useTestProviderConnection,
} from '../hooks/useProviderSettings'
import type {
  ProviderSettingsResponse,
  ProviderSettingsCreate,
  ProviderSettingsUpdate,
} from '../types'

interface EmailProviderSettingsProps {
  locale: string
}

const translations = {
  es: {
    title: 'Configuracion de Proveedores Email',
    subtitle: 'Configure los proveedores de email para enviar notificaciones',
    addProvider: 'Agregar Proveedor',
    filters: 'Filtros',
    filterStatus: 'Estado',
    allStatus: 'Todos',
    active: 'Activo',
    inactive: 'Inactivo',
    clearFilters: 'Limpiar Filtros',
    loading: 'Cargando proveedores...',
    errorLoading: 'Error al cargar proveedores',
    noProviders: 'No hay proveedores Email configurados',
    addFirst: 'Agregar SendGrid',
    provider: 'Proveedor',
    code: 'Codigo',
    apiUrl: 'URL API',
    default: 'Por Defecto',
    status: 'Estado',
    actions: 'Acciones',
    apiKeyConfigured: 'API Key configurada',
    noApiKey: 'Sin API Key',
    gmail: {
      title: 'Gmail SMTP (Actual)',
      description: 'La configuracion de Gmail SMTP esta gestionada via Google Cloud Secret Manager. Los emails transaccionales (verificacion, reset password, 2FA) usan esta configuracion.',
      host: 'smtp.gmail.com',
      port: '587 (TLS)',
      managed: 'Gestionado via Secret Manager',
    },
    createDialog: {
      title: 'Agregar Proveedor Email',
      subtitle: 'Configure un nuevo proveedor de email (ej: SendGrid)',
    },
    editDialog: {
      title: 'Editar Proveedor Email',
      subtitle: 'Actualizar configuracion del proveedor',
    },
    deleteDialog: {
      title: 'Eliminar Proveedor',
      description: 'Esta seguro que desea eliminar este proveedor? Esta accion no se puede deshacer.',
      cancel: 'Cancelar',
      delete: 'Eliminar',
    },
    form: {
      providerCode: 'Codigo del Proveedor',
      providerCodeHint: 'Identificador unico (ej: SENDGRID_EMAIL)',
      providerName: 'Nombre del Proveedor',
      providerNameHint: 'Nombre descriptivo (ej: SendGrid)',
      apiBaseUrl: 'URL Base de la API',
      apiBaseUrlHint: 'URL base para las llamadas API (ej: https://api.sendgrid.com/v3)',
      apiKey: 'API Key',
      apiKeyHint: 'Clave de autenticacion del proveedor',
      apiKeyEdit: 'API Key (dejar vacio para mantener actual)',
      fromEmail: 'Email Remitente',
      fromEmailHint: 'Direccion de email que aparecera como remitente',
      fromName: 'Nombre Remitente',
      fromNameHint: 'Nombre que aparecera como remitente',
      isActive: 'Activo',
      isDefault: 'Establecer como predeterminado',
      cancel: 'Cancelar',
      save: 'Guardar',
      create: 'Crear Proveedor',
      saving: 'Guardando...',
    },
    test: {
      success: 'Conexion exitosa',
      failed: 'Error de conexion',
      testing: 'Probando...',
    },
    sendgrid: {
      title: 'Configuracion SendGrid',
      description: 'SendGrid es un servicio de email transaccional. Obtenga su API Key desde el dashboard de SendGrid.',
      authFormat: 'Formato de autenticacion: Authorization: Bearer {API_KEY}',
      endpoint: 'Endpoint: POST /mail/send',
    },
  },
  fr: {
    title: 'Configuration des Fournisseurs Email',
    subtitle: 'Configurez les fournisseurs email pour envoyer des notifications',
    addProvider: 'Ajouter Fournisseur',
    filters: 'Filtres',
    filterStatus: 'Statut',
    allStatus: 'Tous',
    active: 'Actif',
    inactive: 'Inactif',
    clearFilters: 'Effacer Filtres',
    loading: 'Chargement des fournisseurs...',
    errorLoading: 'Erreur de chargement',
    noProviders: 'Aucun fournisseur Email configure',
    addFirst: 'Ajouter SendGrid',
    provider: 'Fournisseur',
    code: 'Code',
    apiUrl: 'URL API',
    default: 'Par Defaut',
    status: 'Statut',
    actions: 'Actions',
    apiKeyConfigured: 'API Key configuree',
    noApiKey: 'Pas de API Key',
    gmail: {
      title: 'Gmail SMTP (Actuel)',
      description: 'La configuration Gmail SMTP est geree via Google Cloud Secret Manager. Les emails transactionnels (verification, reset password, 2FA) utilisent cette configuration.',
      host: 'smtp.gmail.com',
      port: '587 (TLS)',
      managed: 'Gere via Secret Manager',
    },
    createDialog: {
      title: 'Ajouter Fournisseur Email',
      subtitle: 'Configurer un nouveau fournisseur email (ex: SendGrid)',
    },
    editDialog: {
      title: 'Modifier Fournisseur Email',
      subtitle: 'Mettre a jour la configuration',
    },
    deleteDialog: {
      title: 'Supprimer Fournisseur',
      description: 'Etes-vous sur de vouloir supprimer ce fournisseur? Cette action est irreversible.',
      cancel: 'Annuler',
      delete: 'Supprimer',
    },
    form: {
      providerCode: 'Code Fournisseur',
      providerCodeHint: 'Identifiant unique (ex: SENDGRID_EMAIL)',
      providerName: 'Nom du Fournisseur',
      providerNameHint: 'Nom descriptif (ex: SendGrid)',
      apiBaseUrl: 'URL Base API',
      apiBaseUrlHint: 'URL base pour les appels API (ex: https://api.sendgrid.com/v3)',
      apiKey: 'API Key',
      apiKeyHint: 'Cle d\'authentification du fournisseur',
      apiKeyEdit: 'API Key (laisser vide pour garder actuelle)',
      fromEmail: 'Email Expediteur',
      fromEmailHint: 'Adresse email qui apparaitra comme expediteur',
      fromName: 'Nom Expediteur',
      fromNameHint: 'Nom qui apparaitra comme expediteur',
      isActive: 'Actif',
      isDefault: 'Definir par defaut',
      cancel: 'Annuler',
      save: 'Enregistrer',
      create: 'Creer Fournisseur',
      saving: 'Enregistrement...',
    },
    test: {
      success: 'Connexion reussie',
      failed: 'Echec de connexion',
      testing: 'Test en cours...',
    },
    sendgrid: {
      title: 'Configuration SendGrid',
      description: 'SendGrid est un service d\'email transactionnel. Obtenez votre API Key depuis le dashboard SendGrid.',
      authFormat: 'Format d\'authentification: Authorization: Bearer {API_KEY}',
      endpoint: 'Endpoint: POST /mail/send',
    },
  },
  en: {
    title: 'Email Provider Settings',
    subtitle: 'Configure email providers for sending notifications',
    addProvider: 'Add Provider',
    filters: 'Filters',
    filterStatus: 'Status',
    allStatus: 'All',
    active: 'Active',
    inactive: 'Inactive',
    clearFilters: 'Clear Filters',
    loading: 'Loading providers...',
    errorLoading: 'Error loading providers',
    noProviders: 'No Email providers configured',
    addFirst: 'Add SendGrid',
    provider: 'Provider',
    code: 'Code',
    apiUrl: 'API URL',
    default: 'Default',
    status: 'Status',
    actions: 'Actions',
    apiKeyConfigured: 'API Key configured',
    noApiKey: 'No API Key',
    gmail: {
      title: 'Gmail SMTP (Current)',
      description: 'Gmail SMTP configuration is managed via Google Cloud Secret Manager. Transactional emails (verification, password reset, 2FA) use this configuration.',
      host: 'smtp.gmail.com',
      port: '587 (TLS)',
      managed: 'Managed via Secret Manager',
    },
    createDialog: {
      title: 'Add Email Provider',
      subtitle: 'Configure a new email provider (e.g., SendGrid)',
    },
    editDialog: {
      title: 'Edit Email Provider',
      subtitle: 'Update provider configuration',
    },
    deleteDialog: {
      title: 'Delete Provider',
      description: 'Are you sure you want to delete this provider? This action cannot be undone.',
      cancel: 'Cancel',
      delete: 'Delete',
    },
    form: {
      providerCode: 'Provider Code',
      providerCodeHint: 'Unique identifier (e.g., SENDGRID_EMAIL)',
      providerName: 'Provider Name',
      providerNameHint: 'Descriptive name (e.g., SendGrid)',
      apiBaseUrl: 'API Base URL',
      apiBaseUrlHint: 'Base URL for API calls (e.g., https://api.sendgrid.com/v3)',
      apiKey: 'API Key',
      apiKeyHint: 'Provider authentication key',
      apiKeyEdit: 'API Key (leave empty to keep current)',
      fromEmail: 'From Email',
      fromEmailHint: 'Email address that appears as sender',
      fromName: 'From Name',
      fromNameHint: 'Name that appears as sender',
      isActive: 'Active',
      isDefault: 'Set as default',
      cancel: 'Cancel',
      save: 'Save',
      create: 'Create Provider',
      saving: 'Saving...',
    },
    test: {
      success: 'Connection successful',
      failed: 'Connection failed',
      testing: 'Testing...',
    },
    sendgrid: {
      title: 'SendGrid Configuration',
      description: 'SendGrid is a transactional email service. Get your API Key from the SendGrid dashboard.',
      authFormat: 'Authentication format: Authorization: Bearer {API_KEY}',
      endpoint: 'Endpoint: POST /mail/send',
    },
  },
}

export function EmailProviderSettings({ locale }: EmailProviderSettingsProps) {
  const t = translations[locale as keyof typeof translations] || translations.es

  const [isActiveFilter, setIsActiveFilter] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<ProviderSettingsResponse | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)

  const [formData, setFormData] = useState<ProviderSettingsCreate & { fromEmail?: string; fromName?: string }>({
    providerType: 'email',
    providerName: '',
    providerCode: '',
    apiBaseUrl: '',
    apiKey: '',
    apiSecret: '',
    config: {
      fromEmail: 'noreply@emacsah.com',
      fromName: 'Facil',
      sendEndpoint: '/mail/send',
      templatesEnabled: true,
      trackingEnabled: true,
    },
    isActive: true,
    isDefault: false,
    rateLimitPerMinute: 500,
    retryAttempts: 3,
    timeoutSeconds: 30,
  })

  const { data, isLoading, error } = useProviderSettingsList({
    providerType: 'email',
    isActive: isActiveFilter,
  })

  const createMutation = useCreateProviderSettings()
  const updateMutation = useUpdateProviderSettings()
  const deleteMutation = useDeleteProviderSettings()
  const testMutation = useTestProviderConnection()

  const handleDelete = async () => {
    if (deleteId) {
      await deleteMutation.mutateAsync(deleteId)
      setDeleteId(null)
    }
  }

  const handleCreate = async () => {
    const createData = {
      ...formData,
      config: {
        ...formData.config,
        fromEmail: formData.fromEmail || 'noreply@emacsah.com',
        fromName: formData.fromName || 'Facil',
      },
    }
    await createMutation.mutateAsync(createData)
    setIsCreateDialogOpen(false)
    resetForm()
  }

  const handleUpdate = async () => {
    if (!selectedProvider) return

    const updateData: ProviderSettingsUpdate = {
      providerName: formData.providerName,
      apiBaseUrl: formData.apiBaseUrl,
      apiKey: formData.apiKey || undefined,
      apiSecret: formData.apiSecret || undefined,
      config: {
        ...formData.config,
        fromEmail: formData.fromEmail || 'noreply@emacsah.com',
        fromName: formData.fromName || 'Facil',
      },
      isActive: formData.isActive,
      isDefault: formData.isDefault,
      rateLimitPerMinute: formData.rateLimitPerMinute,
      retryAttempts: formData.retryAttempts,
      timeoutSeconds: formData.timeoutSeconds,
    }

    await updateMutation.mutateAsync({ id: selectedProvider.id, data: updateData })
    setIsEditDialogOpen(false)
    resetForm()
  }

  const handleTest = async (providerCode: string) => {
    setTestingProvider(providerCode)
    await testMutation.mutateAsync({ providerCode })
    setTestingProvider(null)
  }

  const openEditDialog = (provider: ProviderSettingsResponse) => {
    setSelectedProvider(provider)
    const config = provider.config as { fromEmail?: string; fromName?: string } || {}
    setFormData({
      providerType: 'email',
      providerName: provider.providerName,
      providerCode: provider.providerCode,
      apiBaseUrl: provider.apiBaseUrl || '',
      apiKey: '',
      apiSecret: '',
      config: provider.config || {},
      fromEmail: config.fromEmail || '',
      fromName: config.fromName || '',
      isActive: provider.isActive,
      isDefault: provider.isDefault,
      rateLimitPerMinute: provider.rateLimitPerMinute,
      retryAttempts: provider.retryAttempts,
      timeoutSeconds: provider.timeoutSeconds,
    })
    setIsEditDialogOpen(true)
  }

  const resetForm = () => {
    setFormData({
      providerType: 'email',
      providerName: '',
      providerCode: '',
      apiBaseUrl: '',
      apiKey: '',
      apiSecret: '',
      config: {
        fromEmail: 'noreply@emacsah.com',
        fromName: 'Facil',
        sendEndpoint: '/mail/send',
        templatesEnabled: true,
        trackingEnabled: true,
      },
      isActive: true,
      isDefault: false,
      rateLimitPerMinute: 500,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
    setSelectedProvider(null)
  }

  const prefillSendGrid = () => {
    setFormData({
      providerType: 'email',
      providerName: 'SendGrid',
      providerCode: 'SENDGRID_EMAIL',
      apiBaseUrl: 'https://api.sendgrid.com/v3',
      apiKey: '',
      apiSecret: '',
      config: {
        fromEmail: 'noreply@emacsah.com',
        fromName: 'Facil',
        sendEndpoint: '/mail/send',
        templatesEnabled: true,
        trackingEnabled: true,
      },
      fromEmail: 'noreply@emacsah.com',
      fromName: 'Facil',
      isActive: true,
      isDefault: false,
      rateLimitPerMinute: 500,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
  }

  return (
    <div className="space-y-6">
      {/* Gmail SMTP Info Card - Read Only */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-blue-800">
            <Lock className="h-5 w-5" />
            {t.gmail.title}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-blue-700">{t.gmail.description}</p>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-blue-800">Host:</span>
              <span className="ml-2 text-blue-600">{t.gmail.host}</span>
            </div>
            <div>
              <span className="font-medium text-blue-800">Port:</span>
              <span className="ml-2 text-blue-600">{t.gmail.port}</span>
            </div>
          </div>
          <Badge variant="outline" className="bg-blue-100 text-blue-800 border-blue-200">
            <Shield className="mr-1 h-3 w-3" />
            {t.gmail.managed}
          </Badge>
        </CardContent>
      </Card>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{t.title}</h2>
          <p className="text-sm text-muted-foreground">{t.subtitle}</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          {t.addProvider}
        </Button>
      </div>

      {/* SendGrid Info Alert */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>{t.sendgrid.title}</AlertTitle>
        <AlertDescription>
          <p>{t.sendgrid.description}</p>
          <p className="mt-1 text-xs font-mono">{t.sendgrid.authFormat}</p>
          <p className="text-xs font-mono">{t.sendgrid.endpoint}</p>
        </AlertDescription>
      </Alert>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            {t.filters}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t.filterStatus}</label>
              <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={isActiveFilter === undefined ? 'all' : isActiveFilter ? 'active' : 'inactive'}
                onChange={(e) =>
                  setIsActiveFilter(e.target.value === 'all' ? undefined : e.target.value === 'active')
                }
              >
                <option value="all">{t.allStatus}</option>
                <option value="active">{t.active}</option>
                <option value="inactive">{t.inactive}</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => setIsActiveFilter(undefined)}
                className="w-full"
              >
                {t.clearFilters}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Providers List */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto mb-4" />
                <p className="text-muted-foreground">{t.loading}</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
                <p className="text-destructive">{t.errorLoading}</p>
                <p className="text-sm text-muted-foreground">{error.message}</p>
              </div>
            </div>
          ) : !data?.providers || data.providers.length === 0 ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <Mail className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">{t.noProviders}</p>
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => {
                    prefillSendGrid()
                    setIsCreateDialogOpen(true)
                  }}
                >
                  {t.addFirst}
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.provider}</TableHead>
                  <TableHead>{t.code}</TableHead>
                  <TableHead>{t.apiUrl}</TableHead>
                  <TableHead>{t.default}</TableHead>
                  <TableHead>{t.status}</TableHead>
                  <TableHead className="text-right">{t.actions}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.providers.map((provider) => (
                  <TableRow key={provider.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Mail className="h-4 w-4 text-blue-500" />
                        <div>
                          <div className="font-medium">{provider.providerName}</div>
                          <div className="text-sm text-muted-foreground">
                            {provider.hasApiKey ? t.apiKeyConfigured : t.noApiKey}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{provider.providerCode}</TableCell>
                    <TableCell className="max-w-xs truncate">
                      {provider.apiBaseUrl || '-'}
                    </TableCell>
                    <TableCell>
                      {provider.isDefault ? (
                        <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-200">
                          {t.default}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {provider.isActive ? (
                        <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          {t.active}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-200">
                          <XCircle className="mr-1 h-3 w-3" />
                          {t.inactive}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTest(provider.providerCode)}
                          disabled={testingProvider === provider.providerCode}
                          title="Test connection"
                        >
                          {testingProvider === provider.providerCode ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditDialog(provider)}
                          title="Edit"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteId(provider.id)}
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t.createDialog.title}</DialogTitle>
            <DialogDescription>{t.createDialog.subtitle}</DialogDescription>
          </DialogHeader>

          <Alert className="bg-blue-50 border-blue-200">
            <Shield className="h-4 w-4 text-blue-600" />
            <AlertTitle className="text-blue-800">SendGrid</AlertTitle>
            <AlertDescription className="text-blue-700">
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={prefillSendGrid}
              >
                Usar configuracion SendGrid
              </Button>
            </AlertDescription>
          </Alert>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="providerCode">{t.form.providerCode}</Label>
                <Input
                  id="providerCode"
                  value={formData.providerCode}
                  onChange={(e) => setFormData({ ...formData, providerCode: e.target.value.toUpperCase() })}
                  placeholder="SENDGRID_EMAIL"
                />
                <p className="text-xs text-muted-foreground">{t.form.providerCodeHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="providerName">{t.form.providerName}</Label>
                <Input
                  id="providerName"
                  value={formData.providerName}
                  onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
                  placeholder="SendGrid"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiBaseUrl">{t.form.apiBaseUrl}</Label>
              <Input
                id="apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
                placeholder="https://api.sendgrid.com/v3"
              />
              <p className="text-xs text-muted-foreground">{t.form.apiBaseUrlHint}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiKey">{t.form.apiKey}</Label>
              <Input
                id="apiKey"
                type="password"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                placeholder="SG.xxxx..."
              />
              <p className="text-xs text-muted-foreground">{t.form.apiKeyHint}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="fromEmail">{t.form.fromEmail}</Label>
                <Input
                  id="fromEmail"
                  type="email"
                  value={formData.fromEmail || ''}
                  onChange={(e) => setFormData({ ...formData, fromEmail: e.target.value })}
                  placeholder="noreply@emacsah.com"
                />
                <p className="text-xs text-muted-foreground">{t.form.fromEmailHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="fromName">{t.form.fromName}</Label>
                <Input
                  id="fromName"
                  value={formData.fromName || ''}
                  onChange={(e) => setFormData({ ...formData, fromName: e.target.value })}
                  placeholder="Facil"
                />
                <p className="text-xs text-muted-foreground">{t.form.fromNameHint}</p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t">
              <div className="flex items-center space-x-2">
                <Switch
                  id="isActive"
                  checked={formData.isActive}
                  onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
                />
                <Label htmlFor="isActive">{t.form.isActive}</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="isDefault"
                  checked={formData.isDefault}
                  onCheckedChange={(checked) => setFormData({ ...formData, isDefault: checked })}
                />
                <Label htmlFor="isDefault">{t.form.isDefault}</Label>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => { setIsCreateDialogOpen(false); resetForm(); }}>
              {t.form.cancel}
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.form.create}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t.editDialog.title}</DialogTitle>
            <DialogDescription>
              {t.editDialog.subtitle} - {selectedProvider?.providerName}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t.form.providerCode}</Label>
                <Input value={formData.providerCode} disabled />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-providerName">{t.form.providerName}</Label>
                <Input
                  id="edit-providerName"
                  value={formData.providerName}
                  onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-apiBaseUrl">{t.form.apiBaseUrl}</Label>
              <Input
                id="edit-apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-apiKey">{t.form.apiKeyEdit}</Label>
              <Input
                id="edit-apiKey"
                type="password"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                placeholder="Nueva API Key"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-fromEmail">{t.form.fromEmail}</Label>
                <Input
                  id="edit-fromEmail"
                  type="email"
                  value={formData.fromEmail || ''}
                  onChange={(e) => setFormData({ ...formData, fromEmail: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-fromName">{t.form.fromName}</Label>
                <Input
                  id="edit-fromName"
                  value={formData.fromName || ''}
                  onChange={(e) => setFormData({ ...formData, fromName: e.target.value })}
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t">
              <div className="flex items-center space-x-2">
                <Switch
                  id="edit-isActive"
                  checked={formData.isActive}
                  onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
                />
                <Label htmlFor="edit-isActive">{t.form.isActive}</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="edit-isDefault"
                  checked={formData.isDefault}
                  onCheckedChange={(checked) => setFormData({ ...formData, isDefault: checked })}
                />
                <Label htmlFor="edit-isDefault">{t.form.isDefault}</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setIsEditDialogOpen(false); resetForm(); }}>
              {t.form.cancel}
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t.form.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t.deleteDialog.title}</AlertDialogTitle>
            <AlertDialogDescription>{t.deleteDialog.description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t.deleteDialog.cancel}</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              {t.deleteDialog.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
