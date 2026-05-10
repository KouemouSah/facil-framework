/**
 * SmsProviderSettings Component
 * Dedicated page for SMS provider configuration (Infobip, Twilio, etc.)
 * Only shows SMS-type providers with Spanish translations
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
  MessageCircle,
  Info,
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

interface SmsProviderSettingsProps {
  locale: string
}

// Translations object (inline for now, can be moved to i18n files)
const translations = {
  es: {
    title: 'Configuracion del Proveedor SMS',
    subtitle: 'Configure los proveedores de SMS para enviar mensajes',
    addProvider: 'Agregar Proveedor',
    back: 'Volver',
    filters: 'Filtros',
    filterStatus: 'Estado',
    allStatus: 'Todos',
    active: 'Activo',
    inactive: 'Inactivo',
    clearFilters: 'Limpiar Filtros',
    loading: 'Cargando proveedores...',
    errorLoading: 'Error al cargar proveedores',
    noProviders: 'No hay proveedores SMS configurados',
    addFirst: 'Agregar su primer proveedor',
    provider: 'Proveedor',
    code: 'Codigo',
    apiUrl: 'URL API',
    default: 'Por Defecto',
    status: 'Estado',
    actions: 'Acciones',
    apiKeyConfigured: 'Clave API configurada',
    noApiKey: 'Sin clave API',
    createDialog: {
      title: 'Agregar Proveedor SMS',
      subtitle: 'Configure un nuevo proveedor de mensajes SMS',
    },
    editDialog: {
      title: 'Editar Proveedor SMS',
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
      providerCodeHint: 'Identificador unico (ej: infobip_sms)',
      providerName: 'Nombre del Proveedor',
      providerNameHint: 'Nombre descriptivo (ej: Infobip SMS)',
      apiBaseUrl: 'URL Base de la API',
      apiBaseUrlHint: 'URL base para las llamadas API (ej: https://xxxxx.api.infobip.com)',
      apiKey: 'Clave API',
      apiKeyHint: 'Clave de autenticacion del proveedor',
      apiKeyEdit: 'Clave API (dejar vacio para mantener actual)',
      apiSecret: 'Secreto API (opcional)',
      apiSecretHint: 'Secreto adicional si es requerido',
      senderId: 'ID del Remitente (Sender ID)',
      senderIdHint: 'Nombre o numero que aparece como remitente',
      rateLimit: 'Limite por minuto',
      retryAttempts: 'Intentos de reintento',
      timeout: 'Timeout (seg)',
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
    infobip: {
      title: 'Configuracion Infobip',
      description: 'Infobip es un proveedor global de comunicaciones. Use su URL base personalizada y clave API de su cuenta.',
      authFormat: 'Formato de autenticacion: Authorization: App {API_KEY}',
      endpoint: 'Endpoint SMS: POST /sms/3/messages o /sms/2/text/advanced',
    },
  },
  fr: {
    title: 'Configuration du Fournisseur SMS',
    subtitle: 'Configurez les fournisseurs SMS pour envoyer des messages',
    addProvider: 'Ajouter Fournisseur',
    back: 'Retour',
    filters: 'Filtres',
    filterStatus: 'Statut',
    allStatus: 'Tous',
    active: 'Actif',
    inactive: 'Inactif',
    clearFilters: 'Effacer Filtres',
    loading: 'Chargement des fournisseurs...',
    errorLoading: 'Erreur de chargement',
    noProviders: 'Aucun fournisseur SMS configure',
    addFirst: 'Ajouter votre premier fournisseur',
    provider: 'Fournisseur',
    code: 'Code',
    apiUrl: 'URL API',
    default: 'Par Defaut',
    status: 'Statut',
    actions: 'Actions',
    apiKeyConfigured: 'Cle API configuree',
    noApiKey: 'Pas de cle API',
    createDialog: {
      title: 'Ajouter Fournisseur SMS',
      subtitle: 'Configurer un nouveau fournisseur SMS',
    },
    editDialog: {
      title: 'Modifier Fournisseur SMS',
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
      providerCodeHint: 'Identifiant unique (ex: infobip_sms)',
      providerName: 'Nom du Fournisseur',
      providerNameHint: 'Nom descriptif (ex: Infobip SMS)',
      apiBaseUrl: 'URL Base API',
      apiBaseUrlHint: 'URL base pour les appels API (ex: https://xxxxx.api.infobip.com)',
      apiKey: 'Cle API',
      apiKeyHint: 'Cle d\'authentification du fournisseur',
      apiKeyEdit: 'Cle API (laisser vide pour garder actuelle)',
      apiSecret: 'Secret API (optionnel)',
      apiSecretHint: 'Secret additionnel si requis',
      senderId: 'ID Expediteur (Sender ID)',
      senderIdHint: 'Nom ou numero qui apparait comme expediteur',
      rateLimit: 'Limite par minute',
      retryAttempts: 'Tentatives de reessai',
      timeout: 'Timeout (sec)',
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
    infobip: {
      title: 'Configuration Infobip',
      description: 'Infobip est un fournisseur global de communications. Utilisez votre URL base personnalisee et cle API.',
      authFormat: 'Format d\'authentification: Authorization: App {API_KEY}',
      endpoint: 'Endpoint SMS: POST /sms/3/messages ou /sms/2/text/advanced',
    },
  },
  en: {
    title: 'SMS Provider Settings',
    subtitle: 'Configure SMS providers for sending messages',
    addProvider: 'Add Provider',
    back: 'Back',
    filters: 'Filters',
    filterStatus: 'Status',
    allStatus: 'All',
    active: 'Active',
    inactive: 'Inactive',
    clearFilters: 'Clear Filters',
    loading: 'Loading providers...',
    errorLoading: 'Error loading providers',
    noProviders: 'No SMS providers configured',
    addFirst: 'Add your first provider',
    provider: 'Provider',
    code: 'Code',
    apiUrl: 'API URL',
    default: 'Default',
    status: 'Status',
    actions: 'Actions',
    apiKeyConfigured: 'API key configured',
    noApiKey: 'No API key',
    createDialog: {
      title: 'Add SMS Provider',
      subtitle: 'Configure a new SMS provider',
    },
    editDialog: {
      title: 'Edit SMS Provider',
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
      providerCodeHint: 'Unique identifier (e.g., infobip_sms)',
      providerName: 'Provider Name',
      providerNameHint: 'Descriptive name (e.g., Infobip SMS)',
      apiBaseUrl: 'API Base URL',
      apiBaseUrlHint: 'Base URL for API calls (e.g., https://xxxxx.api.infobip.com)',
      apiKey: 'API Key',
      apiKeyHint: 'Provider authentication key',
      apiKeyEdit: 'API Key (leave empty to keep current)',
      apiSecret: 'API Secret (optional)',
      apiSecretHint: 'Additional secret if required',
      senderId: 'Sender ID',
      senderIdHint: 'Name or number that appears as sender',
      rateLimit: 'Rate limit per minute',
      retryAttempts: 'Retry attempts',
      timeout: 'Timeout (sec)',
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
    infobip: {
      title: 'Infobip Configuration',
      description: 'Infobip is a global communications provider. Use your custom base URL and API key from your account.',
      authFormat: 'Authentication format: Authorization: App {API_KEY}',
      endpoint: 'SMS Endpoint: POST /sms/3/messages or /sms/2/text/advanced',
    },
  },
}

export function SmsProviderSettings({ locale }: SmsProviderSettingsProps) {
  const t = translations[locale as keyof typeof translations] || translations.es

  const [isActiveFilter, setIsActiveFilter] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<ProviderSettingsResponse | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)

  // Form state - Only SMS type
  const [formData, setFormData] = useState<ProviderSettingsCreate & { senderId?: string }>({
    providerType: 'sms', // Fixed to SMS
    providerName: '',
    providerCode: '',
    apiBaseUrl: '',
    apiKey: '',
    apiSecret: '',
    config: {
      senderId: '',
      smsEndpoint: '/sms/2/text/advanced',
      deliveryReportEndpoint: '/sms/1/reports',
      supportsUnicode: true,
      maxSegments: 10,
      countryCode: '+240', // Equatorial Guinea
    },
    isActive: true,
    isDefault: false,
    rateLimitPerMinute: 60,
    retryAttempts: 3,
    timeoutSeconds: 30,
  })

  // Always filter by SMS type
  const { data, isLoading, error } = useProviderSettingsList({
    providerType: 'sms',
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
    // Extract senderId to config
    const createData = {
      ...formData,
      config: {
        ...formData.config,
        senderId: formData.senderId || 'Facil',
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
        senderId: formData.senderId || 'Facil',
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
    const config = provider.config as { senderId?: string } || {}
    setFormData({
      providerType: 'sms',
      providerName: provider.providerName,
      providerCode: provider.providerCode,
      apiBaseUrl: provider.apiBaseUrl || '',
      apiKey: '',
      apiSecret: '',
      config: provider.config || {},
      senderId: config.senderId || '',
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
      providerType: 'sms',
      providerName: '',
      providerCode: '',
      apiBaseUrl: '',
      apiKey: '',
      apiSecret: '',
      config: {
        senderId: '',
        smsEndpoint: '/sms/2/text/advanced',
        deliveryReportEndpoint: '/sms/1/reports',
        supportsUnicode: true,
        maxSegments: 10,
        countryCode: '+240',
      },
      isActive: true,
      isDefault: false,
      rateLimitPerMinute: 60,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
    setSelectedProvider(null)
  }

  // Pre-fill Infobip configuration
  const prefillInfobip = () => {
    setFormData({
      providerType: 'sms',
      providerName: 'Infobip SMS',
      providerCode: 'infobip_sms',
      apiBaseUrl: 'https://y45e8g.api.infobip.com',
      apiKey: '',
      apiSecret: '',
      config: {
        senderId: 'Facil',
        smsEndpoint: '/sms/2/text/advanced',
        deliveryReportEndpoint: '/sms/1/reports',
        balanceEndpoint: '/account/1/balance',
        supportsUnicode: true,
        maxSegments: 10,
        countryCode: '+240',
        authHeaderFormat: 'App', // Authorization: App {API_KEY}
      },
      isActive: true,
      isDefault: true,
      rateLimitPerMinute: 60,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
  }

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-muted-foreground">{t.subtitle}</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          {t.addProvider}
        </Button>
      </div>

      {/* Infobip Info Alert */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertTitle>{t.infobip.title}</AlertTitle>
        <AlertDescription>
          <p>{t.infobip.description}</p>
          <p className="mt-1 text-xs font-mono">{t.infobip.authFormat}</p>
          <p className="text-xs font-mono">{t.infobip.endpoint}</p>
        </AlertDescription>
      </Alert>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageCircle className="h-5 w-5" />
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
                <MessageCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">{t.noProviders}</p>
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => {
                    prefillInfobip()
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
                        <MessageCircle className="h-4 w-4 text-blue-500" />
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
                          title="Probar conexion"
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
                          title="Editar"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteId(provider.id)}
                          title="Eliminar"
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


          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="providerCode">{t.form.providerCode}</Label>
                <Input
                  id="providerCode"
                  value={formData.providerCode}
                  onChange={(e) => setFormData({ ...formData, providerCode: e.target.value })}
                  placeholder="infobip_sms"
                />
                <p className="text-xs text-muted-foreground">{t.form.providerCodeHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="providerName">{t.form.providerName}</Label>
                <Input
                  id="providerName"
                  value={formData.providerName}
                  onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
                  placeholder="Infobip SMS"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiBaseUrl">{t.form.apiBaseUrl}</Label>
              <Input
                id="apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
                placeholder="https://xxxxx.api.infobip.com"
              />
              <p className="text-xs text-muted-foreground">{t.form.apiBaseUrlHint}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="apiKey">{t.form.apiKey}</Label>
                <Input
                  id="apiKey"
                  type="password"
                  value={formData.apiKey}
                  onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                  placeholder="Tu clave API"
                />
                <p className="text-xs text-muted-foreground">{t.form.apiKeyHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="senderId">{t.form.senderId}</Label>
                <Input
                  id="senderId"
                  value={formData.senderId || ''}
                  onChange={(e) => setFormData({ ...formData, senderId: e.target.value })}
                  placeholder="Facil"
                />
                <p className="text-xs text-muted-foreground">{t.form.senderIdHint}</p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rateLimitPerMinute">{t.form.rateLimit}</Label>
                <Input
                  id="rateLimitPerMinute"
                  type="number"
                  value={formData.rateLimitPerMinute}
                  onChange={(e) => setFormData({ ...formData, rateLimitPerMinute: parseInt(e.target.value) || 60 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="retryAttempts">{t.form.retryAttempts}</Label>
                <Input
                  id="retryAttempts"
                  type="number"
                  value={formData.retryAttempts}
                  onChange={(e) => setFormData({ ...formData, retryAttempts: parseInt(e.target.value) || 3 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timeoutSeconds">{t.form.timeout}</Label>
                <Input
                  id="timeoutSeconds"
                  type="number"
                  value={formData.timeoutSeconds}
                  onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 30 })}
                />
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

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-apiKey">{t.form.apiKeyEdit}</Label>
                <Input
                  id="edit-apiKey"
                  type="password"
                  value={formData.apiKey}
                  onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                  placeholder="Nueva clave API"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-senderId">{t.form.senderId}</Label>
                <Input
                  id="edit-senderId"
                  value={formData.senderId || ''}
                  onChange={(e) => setFormData({ ...formData, senderId: e.target.value })}
                  placeholder="Facil"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-rateLimitPerMinute">{t.form.rateLimit}</Label>
                <Input
                  id="edit-rateLimitPerMinute"
                  type="number"
                  value={formData.rateLimitPerMinute}
                  onChange={(e) => setFormData({ ...formData, rateLimitPerMinute: parseInt(e.target.value) || 60 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-retryAttempts">{t.form.retryAttempts}</Label>
                <Input
                  id="edit-retryAttempts"
                  type="number"
                  value={formData.retryAttempts}
                  onChange={(e) => setFormData({ ...formData, retryAttempts: parseInt(e.target.value) || 3 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-timeoutSeconds">{t.form.timeout}</Label>
                <Input
                  id="edit-timeoutSeconds"
                  type="number"
                  value={formData.timeoutSeconds}
                  onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 30 })}
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
