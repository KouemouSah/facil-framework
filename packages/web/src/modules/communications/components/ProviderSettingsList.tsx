/**
 * ProviderSettingsList Component
 * Displays and manages communication provider configurations
 */

'use client'

import { useState } from 'react'
import {
  Plus,
  Edit,
  Trash2,
  Settings,
  CheckCircle,
  XCircle,
  Play,
  Loader2,
  MessageCircle,
  Mail,
  Bell,
  MessageSquare,
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import {
  useProviderSettingsList,
  useCreateProviderSettings,
  useUpdateProviderSettings,
  useDeleteProviderSettings,
  useTestProviderConnection,
} from '../hooks/useProviderSettings'
import type {
  CommunicationProviderType,
  ProviderSettingsResponse,
  ProviderSettingsCreate,
  ProviderSettingsUpdate,
} from '../types'

interface ProviderSettingsListProps {
  locale: string
}

const PROVIDER_TYPE_LABELS: Record<CommunicationProviderType, string> = {
  sms: 'SMS',
  email: 'Email',
  push: 'Push Notifications',
  whatsapp: 'WhatsApp',
}

const PROVIDER_TYPE_ICONS: Record<CommunicationProviderType, React.ComponentType<{ className?: string }>> = {
  sms: MessageCircle,
  email: Mail,
  push: Bell,
  whatsapp: MessageSquare,
}

const PROVIDER_TYPE_COLORS: Record<CommunicationProviderType, string> = {
  sms: 'bg-blue-100 text-blue-800 border-blue-200',
  email: 'bg-purple-100 text-purple-800 border-purple-200',
  push: 'bg-orange-100 text-orange-800 border-orange-200',
  whatsapp: 'bg-green-100 text-green-800 border-green-200',
}

export function ProviderSettingsList({ locale: _locale }: ProviderSettingsListProps) {
  const [typeFilter, setTypeFilter] = useState<CommunicationProviderType | 'all'>('all')
  const [isActiveFilter, setIsActiveFilter] = useState<boolean | undefined>(undefined)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<ProviderSettingsResponse | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)

  // Form state
  const [formData, setFormData] = useState<ProviderSettingsCreate>({
    providerType: 'sms',
    providerName: '',
    providerCode: '',
    apiBaseUrl: '',
    apiKey: '',
    apiSecret: '',
    config: {},
    isActive: true,
    isDefault: false,
    rateLimitPerMinute: 60,
    retryAttempts: 3,
    timeoutSeconds: 30,
  })

  const { data, isLoading, error } = useProviderSettingsList({
    providerType: typeFilter !== 'all' ? typeFilter : undefined,
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
    await createMutation.mutateAsync(formData)
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
      config: formData.config,
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
    setFormData({
      providerType: provider.providerType,
      providerName: provider.providerName,
      providerCode: provider.providerCode,
      apiBaseUrl: provider.apiBaseUrl || '',
      apiKey: '', // Don't populate sensitive fields
      apiSecret: '',
      config: provider.config,
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
      config: {},
      isActive: true,
      isDefault: false,
      rateLimitPerMinute: 60,
      retryAttempts: 3,
      timeoutSeconds: 30,
    })
    setSelectedProvider(null)
  }

  const getProviderTypeBadge = (type: CommunicationProviderType) => {
    const Icon = PROVIDER_TYPE_ICONS[type]
    return (
      <Badge variant="outline" className={PROVIDER_TYPE_COLORS[type]}>
        <Icon className="mr-1 h-3 w-3" />
        {PROVIDER_TYPE_LABELS[type]}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Provider Settings</h1>
          <p className="text-muted-foreground">
            Configure communication providers (SMS, Email, Push, WhatsApp)
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Add Provider
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Filters
          </CardTitle>
          <CardDescription>Filter provider configurations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">Provider Type</label>
              <Select
                value={typeFilter}
                onValueChange={(value) => setTypeFilter(value as CommunicationProviderType | 'all')}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="sms">SMS</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="push">Push</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <Select
                value={isActiveFilter === undefined ? 'all' : isActiveFilter ? 'active' : 'inactive'}
                onValueChange={(value) =>
                  setIsActiveFilter(value === 'all' ? undefined : value === 'active')
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end">
              <Button
                variant="outline"
                onClick={() => {
                  setTypeFilter('all')
                  setIsActiveFilter(undefined)
                }}
                className="w-full"
              >
                Clear Filters
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
                <p className="text-muted-foreground">Loading providers...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
                <p className="text-destructive">Failed to load providers</p>
                <p className="text-sm text-muted-foreground">{error.message}</p>
              </div>
            </div>
          ) : !data?.providers || data.providers.length === 0 ? (
            <div className="flex items-center justify-center p-12">
              <div className="text-center">
                <Settings className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-muted-foreground">No providers configured</p>
                <Button
                  variant="link"
                  className="mt-2"
                  onClick={() => setIsCreateDialogOpen(true)}
                >
                  Add your first provider
                </Button>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Code</TableHead>
                  <TableHead>API URL</TableHead>
                  <TableHead>Default</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.providers.map((provider) => (
                  <TableRow key={provider.id}>
                    <TableCell>
                      <div className="font-medium">{provider.providerName}</div>
                      <div className="text-sm text-muted-foreground">
                        {provider.hasApiKey ? 'API Key configured' : 'No API key'}
                      </div>
                    </TableCell>
                    <TableCell>{getProviderTypeBadge(provider.providerType)}</TableCell>
                    <TableCell className="font-mono text-sm">{provider.providerCode}</TableCell>
                    <TableCell className="max-w-xs truncate">
                      {provider.apiBaseUrl || '-'}
                    </TableCell>
                    <TableCell>
                      {provider.isDefault ? (
                        <Badge variant="outline" className="bg-yellow-100 text-yellow-800 border-yellow-200">
                          Default
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {provider.isActive ? (
                        <Badge variant="outline" className="bg-green-100 text-green-800 border-green-200">
                          <CheckCircle className="mr-1 h-3 w-3" />
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-gray-100 text-gray-800 border-gray-200">
                          <XCircle className="mr-1 h-3 w-3" />
                          Inactive
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
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteId(provider.id)}
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
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add Provider Configuration</DialogTitle>
            <DialogDescription>
              Configure a new communication provider
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="providerType">Provider Type</Label>
                <Select
                  value={formData.providerType}
                  onValueChange={(value) => setFormData({ ...formData, providerType: value as CommunicationProviderType })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sms">SMS</SelectItem>
                    <SelectItem value="email">Email</SelectItem>
                    <SelectItem value="push">Push Notifications</SelectItem>
                    <SelectItem value="whatsapp">WhatsApp</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="providerCode">Provider Code</Label>
                <Input
                  id="providerCode"
                  value={formData.providerCode}
                  onChange={(e) => setFormData({ ...formData, providerCode: e.target.value })}
                  placeholder="infobip_sms"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="providerName">Provider Name</Label>
              <Input
                id="providerName"
                value={formData.providerName}
                onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
                placeholder="Infobip SMS"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="apiBaseUrl">API Base URL</Label>
              <Input
                id="apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
                placeholder="https://api.infobip.com"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="apiKey">API Key</Label>
                <Input
                  id="apiKey"
                  type="password"
                  value={formData.apiKey}
                  onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                  placeholder="Enter API key"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="apiSecret">API Secret (optional)</Label>
                <Input
                  id="apiSecret"
                  type="password"
                  value={formData.apiSecret}
                  onChange={(e) => setFormData({ ...formData, apiSecret: e.target.value })}
                  placeholder="Enter API secret"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="rateLimitPerMinute">Rate Limit/min</Label>
                <Input
                  id="rateLimitPerMinute"
                  type="number"
                  value={formData.rateLimitPerMinute}
                  onChange={(e) => setFormData({ ...formData, rateLimitPerMinute: parseInt(e.target.value) || 60 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="retryAttempts">Retry Attempts</Label>
                <Input
                  id="retryAttempts"
                  type="number"
                  value={formData.retryAttempts}
                  onChange={(e) => setFormData({ ...formData, retryAttempts: parseInt(e.target.value) || 3 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timeoutSeconds">Timeout (sec)</Label>
                <Input
                  id="timeoutSeconds"
                  type="number"
                  value={formData.timeoutSeconds}
                  onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 30 })}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Switch
                  id="isActive"
                  checked={formData.isActive}
                  onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
                />
                <Label htmlFor="isActive">Active</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="isDefault"
                  checked={formData.isDefault}
                  onCheckedChange={(checked) => setFormData({ ...formData, isDefault: checked })}
                />
                <Label htmlFor="isDefault">Set as Default</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Provider
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Provider Configuration</DialogTitle>
            <DialogDescription>
              Update provider settings for {selectedProvider?.providerName}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Provider Type</Label>
                <Input value={PROVIDER_TYPE_LABELS[formData.providerType]} disabled />
              </div>
              <div className="space-y-2">
                <Label>Provider Code</Label>
                <Input value={formData.providerCode} disabled />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-providerName">Provider Name</Label>
              <Input
                id="edit-providerName"
                value={formData.providerName}
                onChange={(e) => setFormData({ ...formData, providerName: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-apiBaseUrl">API Base URL</Label>
              <Input
                id="edit-apiBaseUrl"
                value={formData.apiBaseUrl}
                onChange={(e) => setFormData({ ...formData, apiBaseUrl: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-apiKey">API Key (leave empty to keep current)</Label>
                <Input
                  id="edit-apiKey"
                  type="password"
                  value={formData.apiKey}
                  onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                  placeholder="Enter new API key"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-apiSecret">API Secret (leave empty to keep current)</Label>
                <Input
                  id="edit-apiSecret"
                  type="password"
                  value={formData.apiSecret}
                  onChange={(e) => setFormData({ ...formData, apiSecret: e.target.value })}
                  placeholder="Enter new API secret"
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="edit-rateLimitPerMinute">Rate Limit/min</Label>
                <Input
                  id="edit-rateLimitPerMinute"
                  type="number"
                  value={formData.rateLimitPerMinute}
                  onChange={(e) => setFormData({ ...formData, rateLimitPerMinute: parseInt(e.target.value) || 60 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-retryAttempts">Retry Attempts</Label>
                <Input
                  id="edit-retryAttempts"
                  type="number"
                  value={formData.retryAttempts}
                  onChange={(e) => setFormData({ ...formData, retryAttempts: parseInt(e.target.value) || 3 })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-timeoutSeconds">Timeout (sec)</Label>
                <Input
                  id="edit-timeoutSeconds"
                  type="number"
                  value={formData.timeoutSeconds}
                  onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 30 })}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Switch
                  id="edit-isActive"
                  checked={formData.isActive}
                  onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
                />
                <Label htmlFor="edit-isActive">Active</Label>
              </div>
              <div className="flex items-center space-x-2">
                <Switch
                  id="edit-isDefault"
                  checked={formData.isDefault}
                  onCheckedChange={(checked) => setFormData({ ...formData, isDefault: checked })}
                />
                <Label htmlFor="edit-isDefault">Set as Default</Label>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updateMutation.isPending}>
              {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteId !== null} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Provider Configuration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this provider configuration? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-destructive text-destructive-foreground">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
