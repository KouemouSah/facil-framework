/**
 * WhatsAppProviderSettings Component
 * Configuration page for WhatsApp Business API (Meta)
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
  MessageSquare,
  Shield,
  Info,
  ExternalLink,
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

interface WhatsAppProviderSettingsProps {
  locale: string
}

const translations = {
  es: {
    title: 'Configuracion de WhatsApp Business',
    subtitle: 'Configure la integracion con Meta WhatsApp Business API',
    addProvider: 'Agregar Configuracion',
    filters: 'Filtros',
    filterStatus: 'Estado',
    allStatus: 'Todos',
    active: 'Activo',
    inactive: 'Inactivo',
    clearFilters: 'Limpiar Filtros',
    loading: 'Cargando configuracion...',
    errorLoading: 'Error al cargar configuracion',
    noProviders: 'No hay configuracion de WhatsApp',
    addFirst: 'Configurar Meta WhatsApp',
    provider: 'Proveedor',
    code: 'Codigo',
    phoneNumberId: 'Phone Number ID',
    default: 'Por Defecto',
    status: 'Estado',
    actions: 'Acciones',
    accessTokenConfigured: 'Access Token configurado',
    noAccessToken: 'Sin Access Token',
    meta: {
      title: 'Meta WhatsApp Business API',
      description: 'Para usar WhatsApp Business API necesita una cuenta de Meta Business verificada. Los mensajes se envian via la API de Graph de Facebook.',
      requirements: 'Requisitos: Meta Business Account, WhatsApp Business Account, Phone Number verificado.',
      docsLink: 'Ver documentacion de Meta',
    },
    createDialog: {
      title: 'Configurar WhatsApp Business',
      subtitle: 'Configure la conexion con Meta WhatsApp Business API',
    },
    editDialog: {
      title: 'Editar Configuracion WhatsApp',
      subtitle: 'Actualizar configuracion de WhatsApp Business',
    },
    deleteDialog: {
      title: 'Eliminar Configuracion',
      description: 'Esta seguro que desea eliminar esta configuracion? Esta accion no se puede deshacer.',
      cancel: 'Cancelar',
      delete: 'Eliminar',
    },
    form: {
      providerCode: 'Codigo del Proveedor',
      providerCodeHint: 'Identificador unico (ej: META_WHATSAPP)',
      providerName: 'Nombre del Proveedor',
      providerNameHint: 'Nombre descriptivo (ej: Meta WhatsApp Business)',
      apiBaseUrl: 'URL Base de la API',
      apiBaseUrlHint: 'URL base de Graph API (ej: https://graph.facebook.com/v17.0)',
      accessToken: 'Access Token',
      accessTokenHint: 'Token de acceso permanente de Meta Business',
      accessTokenEdit: 'Access Token (dejar vacio para mantener actual)',
      phoneNumberId: 'Phone Number ID',
      phoneNumberIdHint: 'ID del numero de telefono de WhatsApp Business',
      businessAccountId: 'Business Account ID',
      businessAccountIdHint: 'ID de la cuenta de WhatsApp Business',
      webhookVerifyToken: 'Webhook Verify Token',
      webhookVerifyTokenHint: 'Token para verificar webhooks entrantes',
      isActive: 'Activo',
      isDefault: 'Establecer como predeterminado',
      cancel: 'Cancelar',
      save: 'Guardar',
      create: 'Crear Configuracion',
      saving: 'Guardando...',
    },
    test: {
      success: 'Conexion exitosa',
      failed: 'Error de conexion',
      testing: 'Probando...',
    },
  },
  fr: {
    title: 'Configuration WhatsApp Business',
    subtitle: 'Configurez l\'integration avec Meta WhatsApp Business API',
    addProvider: 'Ajouter Configuration',
    filters: 'Filtres',
    filterStatus: 'Statut',
    allStatus: 'Tous',
    active: 'Actif',
    inactive: 'Inactif',
    clearFilters: 'Effacer Filtres',
    loading: 'Chargement de la configuration...',
    errorLoading: 'Erreur de chargement',
    noProviders: 'Aucune configuration WhatsApp',
    addFirst: 'Configurer Meta WhatsApp',
    provider: 'Fournisseur',
    code: 'Code',
    phoneNumberId: 'Phone Number ID',
    default: 'Par Defaut',
    status: 'Statut',
    actions: 'Actions',
    accessTokenConfigured: 'Access Token configure',
    noAccessToken: 'Pas de Access Token',
    meta: {
      title: 'Meta WhatsApp Business API',
      description: 'Pour utiliser WhatsApp Business API, vous avez besoin d\'un compte Meta Business verifie. Les messages sont envoyes via l\'API Graph de Facebook.',
      requirements: 'Prerequis: Meta Business Account, WhatsApp Business Account, Numero de telephone verifie.',
      docsLink: 'Voir documentation Meta',
    },
    createDialog: {
      title: 'Configurer WhatsApp Business',
      subtitle: 'Configurer la connexion avec Meta WhatsApp Business API',
    },
    editDialog: {
      title: 'Modifier Configuration WhatsApp',
      subtitle: 'Mettre a jour la configuration WhatsApp Business',
    },
    deleteDialog: {
      title: 'Supprimer Configuration',
      description: 'Etes-vous sur de vouloir supprimer cette configuration? Cette action est irreversible.',
      cancel: 'Annuler',
      delete: 'Supprimer',
    },
    form: {
      providerCode: 'Code Fournisseur',
      providerCodeHint: 'Identifiant unique (ex: META_WHATSAPP)',
      providerName: 'Nom du Fournisseur',
      providerNameHint: 'Nom descriptif (ex: Meta WhatsApp Business)',
      apiBaseUrl: 'URL Base API',
      apiBaseUrlHint: 'URL base de Graph API (ex: https://graph.facebook.com/v17.0)',
      accessToken: 'Access Token',
      accessTokenHint: 'Token d\'acces permanent de Meta Business',
      accessTokenEdit: 'Access Token (laisser vide pour garder actuel)',
      phoneNumberId: 'Phone Number ID',
      phoneNumberIdHint: 'ID du numero de telephone WhatsApp Business',
      businessAccountId: 'Business Account ID',
      businessAccountIdHint: 'ID du compte WhatsApp Business',
      webhookVerifyToken: 'Webhook Verify Token',
      webhookVerifyTokenHint: 'Token pour verifier les webhooks entrants',
      isActive: 'Actif',
      isDefault: 'Definir par defaut',
      cancel: 'Annuler',
      save: 'Enregistrer',
      create: 'Creer Configuration',
      saving: 'Enregistrement...',
    },
    test: {
      success: 'Connexion reussie',
      failed: 'Echec de connexion',
      testing: 'Test en cours...',
    },
  },
  en: {
    title: 'WhatsApp Business Settings',
    subtitle: 'Configure the integration with Meta WhatsApp Business API',
    addProvider: 'Add Configuration',
    filters: 'Filters',
    filterStatus: 'Status',
    allStatus: 'All',
    active: 'Active',
    inactive: 'Inactive',
    clearFilters: 'Clear Filters',
    loading: 'Loading configuration...',
    errorLoading: 'Error loading configuration',
    noProviders: 'No WhatsApp configuration',
    addFirst: 'Configure Meta WhatsApp',
    provider: 'Provider',
    code: 'Code',
    phoneNumberId: 'Phone Number ID',
    default: 'Default',
    status: 'Status',
    actions: 'Actions',
    accessTokenConfigured: 'Access Token configured',
    noAccessToken: 'No Access Token',
    meta: {
      title: 'Meta WhatsApp Business API',
      description: 'To use WhatsApp Business API you need a verified Meta Business account. Messages are sent via Facebook\'s Graph API.',
      requirements: 'Requirements: Meta Business Account, WhatsApp Business Account, Verified Phone Number.',
      docsLink: 'View Meta documentation',
    },
    createDialog: {
      title: 'Configure WhatsApp Business',
      subtitle: 'Configure connection with Meta WhatsApp Business API',
    },
    editDialog: {
      title: 'Edit WhatsApp Configuration',
      subtitle: 'Update WhatsApp Business configuration',
    },
    deleteDialog: {
      title: 'Delete Configuration',
      description: 'Are you sure you want to delete this configuration? This action cannot be undone.',
      cancel: 'Cancel',
      delete: 'Delete',
    },
    form: {
      providerCode: 'Provider Code',
      providerCodeHint: 'Unique identifier (e.g., META_WHATSAPP)',
      providerName: 'Provider Name',
      providerNameHint: 'Descriptive name (e.g., Meta WhatsApp Business)',
      apiBaseUrl: 'API Base URL',
      apiBaseUrlHint: 'Graph API base URL (e.g., https://graph.facebook.com/v17.0)',
      accessToken: 'Access Token',
      accessTokenHint: 'Permanent access token from Meta Business',
      accessTokenEdit: 'Access Token (leave empty to keep current)',
      phoneNumberId: 'Phone Number ID',
      phoneNumberIdHint: 'WhatsApp Business phone number ID',
      businessAccountId: 'Business Account ID',
      businessAccountIdHint: 'WhatsApp Business account ID',
      webhookVerifyToken: 'Webhook Verify Token',
      webhookVerifyTokenHint: 'Token to verify incoming webhooks',
      isActive: 'Active',
      isDefault: 'Set as default',
      cancel: 'Cancel',
      save: 'Save',
      create: 'Create Configuration',
      saving: 'Saving...',
    },
    test: {
      success: 'Connection successful',
      failed: 'Connection failed',
      testing: 'Testing...',
    },
  },
}

export function WhatsAppProviderSettings({ locale }: WhatsAppProviderSettingsProps) {
  const t = translations[locale as keyof typeof translations] || translations.es

  const [isActiveFilter, setIsActiveFilter] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<ProviderSettingsResponse | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)

  const [formData, setFormData] = useState<ProviderSettingsCreate & {
    phoneNumberId?: string
    businessAccountId?: string
    webhookVerifyToken?: string
  }>({
    providerType: 'whatsapp',
    providerName: '',
    providerCode: '',
    apiBaseUrl: 'https://graph.facebook.com/v17.0',
    apiKey: '',
    apiSecret: '',
    config: {
      phoneNumberId: '',
      businessAccountId: '',
      sendEndpoint: '/messages',
      templatesEndpoint: '/message_templates',
      webhookVerifyToken: 'taxasge_whatsapp_verify',
    },
    isActive: false,
    isDefault: true,
    rateLimitPerMinute: 100,
    retryAttempts: 3,
    timeoutSeconds: 30,
  })

  const { data, isLoading, error } = useProviderSettingsList({
    providerType: 'whatsapp',
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
        phoneNumberId: formData.phoneNumberId || '',
        businessAccountId: formData.businessAccountId || '',
        webhookVerifyToken: formData.webhookVerifyToken || 'taxasge_whatsapp_verify',
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
        phoneNumberId: formData.phoneNumberId || '',
        businessAccountId: formData.businessAccountId || '',
        webhookVerifyToken: formData.webhookVerifyToken || 'taxasge_whatsapp_verify',
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
    const config = provider.config as {
      phoneNumberId?: string
      businessAccountId?: string
      webhookVerifyToken?: string
    } || {}
    setFormData({
      providerType: 'whatsapp',
      providerName: provider.providerName,
      providerCode: provider.providerCode,
      apiBaseUrl: provider.apiBaseUrl || 'https://graph.facebook.com/v17.0',
      apiKey: '',
      apiSecret: '',
      config: provider.config || {},
      phoneNumberId: config.phoneNumberId || '',
      businessAccountId: config.businessAccountId || '',
      webhookVerifyToken: config.webhookVerifyToken || '',
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
      providerType: 'whatsapp',
      providerName: '',
      providerCode: '',
      apiBaseUrl: 'https://graph.facebook.com/v17.0',
      apiKey: '',
      apiSecret: '',
      config: {
        phoneNumberId: '',
        businessAccountId: '',
        sendEndpoint: '/messages',
        templatesEndpoint: '/message_templates',
        webhookVerifyToken: 'taxasge_whatsapp_verify',
      },
      isActive: false,
      isDefault: true,
      rateLimitPerMinute: 100,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
    setSelectedProvider(null)
  }

  const prefillMeta = () => {
    setFormData({
      providerType: 'whatsapp',
      providerName: 'Meta WhatsApp Business',
      providerCode: 'META_WHATSAPP',
      apiBaseUrl: 'https://graph.facebook.com/v17.0',
      apiKey: '',
      apiSecret: '',
      config: {
        phoneNumberId: '',
        businessAccountId: '',
        sendEndpoint: '/messages',
        templatesEndpoint: '/message_templates',
        webhookVerifyToken: 'taxasge_whatsapp_verify',
      },
      phoneNumberId: '',
      businessAccountId: '',
      webhookVerifyToken: 'taxasge_whatsapp_verify',
      isActive: false,
      isDefault: true,
      rateLimitPerMinute: 100,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
  }

  return (
    <div className="space-y-6">
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

      {/* Meta WhatsApp Info Alert */}
      <Alert className="border-green-200 bg-green-50/50">
        <Info className="h-4 w-4 text-green-600" />
        <AlertTitle className="text-green-800">{t.meta.title}</AlertTitle>
        <AlertDescription className="text-green-700">
          <p>{t.meta.description}</p>
          <p className="mt-1 text-sm">{t.meta.requirements}</p>
          <a
            href="https://developers.facebook.com/docs/whatsapp/cloud-api/get-started"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-2 text-sm text-green-700 hover:underline"
          >
            {t.meta.docsLink}
            <ExternalLink className="h-3 w-3" />
          </a>
        </AlertDescription>
      </Alert>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
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
                <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">{t.noProviders}</p>
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => {
                    prefillMeta()
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
                  <TableHead>{t.phoneNumberId}</TableHead>
                  <TableHead>{t.default}</TableHead>
                  <TableHead>{t.status}</TableHead>
                  <TableHead className="text-right">{t.actions}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.providers.map((provider) => {
                  const config = provider.config as { phoneNumberId?: string } || {}
                  return (
                    <TableRow key={provider.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <MessageSquare className="h-4 w-4 text-green-500" />
                          <div>
                            <div className="font-medium">{provider.providerName}</div>
                            <div className="text-sm text-muted-foreground">
                              {provider.hasApiKey ? t.accessTokenConfigured : t.noAccessToken}
                            </div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-sm">{provider.providerCode}</TableCell>
                      <TableCell className="font-mono text-sm">
                        {config.phoneNumberId || '-'}
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
                  )
                })}
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

          <Alert className="bg-green-50 border-green-200">
            <Shield className="h-4 w-4 text-green-600" />
            <AlertTitle className="text-green-800">Meta WhatsApp</AlertTitle>
            <AlertDescription className="text-green-700">
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={prefillMeta}
              >
                Usar configuracion Meta
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
                  placeholder="META_WHATSAPP"
                />
                <p className="text-xs text-muted-foreground">{t.form.providerCodeHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="providerName">{t.form.providerName}</Label>
                <Input
                  id="providerName"
                  value={formData.providerName}
                  onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
                  placeholder="Meta WhatsApp Business"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiBaseUrl">{t.form.apiBaseUrl}</Label>
              <Input
                id="apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
                placeholder="https://graph.facebook.com/v17.0"
              />
              <p className="text-xs text-muted-foreground">{t.form.apiBaseUrlHint}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiKey">{t.form.accessToken}</Label>
              <Input
                id="apiKey"
                type="password"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                placeholder="EAAxxxx..."
              />
              <p className="text-xs text-muted-foreground">{t.form.accessTokenHint}</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="phoneNumberId">{t.form.phoneNumberId}</Label>
                <Input
                  id="phoneNumberId"
                  value={formData.phoneNumberId || ''}
                  onChange={(e) => setFormData({ ...formData, phoneNumberId: e.target.value })}
                  placeholder="123456789012345"
                />
                <p className="text-xs text-muted-foreground">{t.form.phoneNumberIdHint}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="businessAccountId">{t.form.businessAccountId}</Label>
                <Input
                  id="businessAccountId"
                  value={formData.businessAccountId || ''}
                  onChange={(e) => setFormData({ ...formData, businessAccountId: e.target.value })}
                  placeholder="123456789012345"
                />
                <p className="text-xs text-muted-foreground">{t.form.businessAccountIdHint}</p>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webhookVerifyToken">{t.form.webhookVerifyToken}</Label>
              <Input
                id="webhookVerifyToken"
                value={formData.webhookVerifyToken || ''}
                onChange={(e) => setFormData({ ...formData, webhookVerifyToken: e.target.value })}
                placeholder="taxasge_whatsapp_verify"
              />
              <p className="text-xs text-muted-foreground">{t.form.webhookVerifyTokenHint}</p>
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
              <Label htmlFor="edit-apiKey">{t.form.accessTokenEdit}</Label>
              <Input
                id="edit-apiKey"
                type="password"
                value={formData.apiKey}
                onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                placeholder="Nuevo Access Token"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-phoneNumberId">{t.form.phoneNumberId}</Label>
                <Input
                  id="edit-phoneNumberId"
                  value={formData.phoneNumberId || ''}
                  onChange={(e) => setFormData({ ...formData, phoneNumberId: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-businessAccountId">{t.form.businessAccountId}</Label>
                <Input
                  id="edit-businessAccountId"
                  value={formData.businessAccountId || ''}
                  onChange={(e) => setFormData({ ...formData, businessAccountId: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-webhookVerifyToken">{t.form.webhookVerifyToken}</Label>
              <Input
                id="edit-webhookVerifyToken"
                value={formData.webhookVerifyToken || ''}
                onChange={(e) => setFormData({ ...formData, webhookVerifyToken: e.target.value })}
              />
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
