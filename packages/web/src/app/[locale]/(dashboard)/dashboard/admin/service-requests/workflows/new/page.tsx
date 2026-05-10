'use client'

/**
 * New Workflow Page
 *
 * Create a new dynamic workflow with entity selection.
 * Only creates is_generic=true workflows (dynamic, editable).
 * Predefined workflows are synced from Python code.
 *
 * @module dashboard/admin/service-requests/workflows/new
 */

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  GitBranch,
  Building2,
  Tag,
  Clock,
  Settings,
  Plus,
  X,
} from 'lucide-react'
import { useCreateWorkflow, useWorkflows } from '@/modules/service-requests-admin'
import { WORKFLOW_CATEGORIES_MAP, WORKFLOW_TYPES } from '@/modules/service-requests-admin'
import type { WorkflowCreate, WorkflowType } from '@/modules/service-requests-admin'
import { useEntitiesSimple } from '@/modules/cities/hooks'
import { cn } from '@/lib/utils'

export default function NewWorkflowPage() {
  const _t = useTranslations('admin.serviceRequests.workflows')
  const tCommon = useTranslations('common')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  // Form state
  const [formData, setFormData] = useState<WorkflowCreate>({
    code: '',
    name_es: '',
    description_es: '',
    category: '',
    entity_code: '',
    workflow_type: 'standard',
    requires_agent_validation: true,
    requires_appointment: false,
    is_generic: true, // Always true for dynamic workflows
    sla_hours: 48,
    display_order: 100,
    is_active: true,
    parent_workflow_code: null,
    tags: [],
    is_parent: false,
  })
  const [newTag, setNewTag] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})

  // Queries
  const { data: entities, isLoading: loadingEntities } = useEntitiesSimple(true)
  const { data: workflows, isLoading: loadingWorkflows } = useWorkflows({ is_parent: true })

  // Mutation
  const createWorkflowMutation = useCreateWorkflow()

  // Parent workflows for grouping (only is_parent=true)
  const parentWorkflows = workflows?.filter((wf) => wf.is_parent) || []

  // Handle form field change
  const handleChange = (field: keyof WorkflowCreate, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }))
    // Clear error when field changes
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev }
        delete newErrors[field]
        return newErrors
      })
    }
  }

  // Auto-generate code from name
  const handleNameChange = (name: string) => {
    handleChange('name_es', name)
    // Auto-generate code if code is empty or was auto-generated
    if (!formData.code || formData.code === generateCode(formData.name_es)) {
      handleChange('code', generateCode(name))
    }
  }

  const generateCode = (name: string): string => {
    return name
      .toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // Remove accents
      .replace(/[^A-Z0-9_]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_|_$/g, '')
      .substring(0, 50)
  }

  // Handle tag management
  const addTag = () => {
    const tag = newTag.trim().toLowerCase()
    if (tag && !formData.tags?.includes(tag)) {
      handleChange('tags', [...(formData.tags || []), tag])
      setNewTag('')
    }
  }

  const removeTag = (tagToRemove: string) => {
    handleChange(
      'tags',
      (formData.tags || []).filter((tag) => tag !== tagToRemove)
    )
  }

  // Validate form
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {}

    if (!formData.code.trim()) {
      newErrors.code = 'El código es requerido'
    } else if (!/^[A-Z][A-Z0-9_]+$/.test(formData.code)) {
      newErrors.code = 'El código debe comenzar con una letra y solo contener mayúsculas, números y guiones bajos'
    }

    if (!formData.name_es.trim()) {
      newErrors.name_es = 'El nombre es requerido'
    }

    if (!formData.category) {
      newErrors.category = 'La categoría es requerida'
    }

    if (!formData.entity_code) {
      newErrors.entity_code = 'La entidad es requerida'
    }

    if (formData.sla_hours && formData.sla_hours < 1) {
      newErrors.sla_hours = 'El SLA debe ser al menos 1 hora'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validate()) return

    try {
      await createWorkflowMutation.mutateAsync(formData)
      router.push(`/${locale}/dashboard/admin/service-requests/workflows/${formData.code}?mode=edit`)
    } catch {
      // Error is handled by mutation hook
    }
  }

  // Go back
  const handleBack = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/workflows`)
  }

  const isLoading = loadingEntities || loadingWorkflows

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Nuevo Workflow</h1>
          <p className="text-muted-foreground">Crear un nuevo workflow dinámico</p>
        </div>
      </div>

      {/* Info Banner */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-blue-600 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium">Workflow Dinámico</p>
              <p className="mt-1">
                Este formulario crea workflows dinámicos (editables). Los workflows predefinidos
                (PASAPORTE, RESIDENCIA, etc.) se sincronizan desde el código Python usando el
                endpoint de sincronización.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <form onSubmit={handleSubmit}>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Basic Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Información Básica
              </CardTitle>
              <CardDescription>Identificación y descripción del workflow</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Name */}
              <div className="space-y-2">
                <Label htmlFor="name_es">Nombre (Español) *</Label>
                <Input
                  id="name_es"
                  value={formData.name_es}
                  onChange={(e) => handleNameChange(e.target.value)}
                  placeholder="Ej: Solicitud de Certificado"
                  className={cn(errors.name_es && 'border-destructive')}
                />
                {errors.name_es && (
                  <p className="text-sm text-destructive">{errors.name_es}</p>
                )}
              </div>

              {/* Code */}
              <div className="space-y-2">
                <Label htmlFor="code">Código Único *</Label>
                <Input
                  id="code"
                  value={formData.code}
                  onChange={(e) => handleChange('code', e.target.value.toUpperCase())}
                  placeholder="SOLICITUD_CERTIFICADO"
                  className={cn('font-mono', errors.code && 'border-destructive')}
                />
                <p className="text-xs text-muted-foreground">
                  Solo letras mayúsculas, números y guiones bajos
                </p>
                {errors.code && <p className="text-sm text-destructive">{errors.code}</p>}
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="description_es">Descripción</Label>
                <Textarea
                  id="description_es"
                  value={formData.description_es || ''}
                  onChange={(e) => handleChange('description_es', e.target.value)}
                  placeholder="Descripción del trámite..."
                  rows={3}
                />
              </div>

              {/* Category */}
              <div className="space-y-2">
                <Label htmlFor="category">Categoría *</Label>
                <Select
                  value={formData.category}
                  onValueChange={(value) => handleChange('category', value)}
                >
                  <SelectTrigger className={cn(errors.category && 'border-destructive')}>
                    <SelectValue placeholder="Seleccionar categoría" />
                  </SelectTrigger>
                  <SelectContent>
                    {WORKFLOW_CATEGORIES_MAP.map((cat) => (
                      <SelectItem key={cat.value} value={cat.value}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.category && (
                  <p className="text-sm text-destructive">{errors.category}</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Entity & Organization */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5" />
                Entidad y Organización
              </CardTitle>
              <CardDescription>Asignación de entidad responsable y agrupación</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Entity Selection */}
              <div className="space-y-2">
                <Label htmlFor="entity_code">Entidad Responsable *</Label>
                <Select
                  value={formData.entity_code}
                  onValueChange={(value) => handleChange('entity_code', value)}
                  disabled={loadingEntities}
                >
                  <SelectTrigger className={cn(errors.entity_code && 'border-destructive')}>
                    <SelectValue
                      placeholder={loadingEntities ? 'Cargando entidades...' : 'Seleccionar entidad'}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {entities?.map((entity) => (
                      <SelectItem key={entity.id} value={entity.code}>
                        <div className="flex flex-col">
                          <span className="font-medium">{entity.code}</span>
                          <span className="text-xs text-muted-foreground">{entity.name}</span>
                        </div>
                      </SelectItem>
                    ))}
                    {/* Also allow manual entry for codes not in entities table */}
                    <SelectItem value="GENERAL">
                      <div className="flex flex-col">
                        <span className="font-medium">GENERAL</span>
                        <span className="text-xs text-muted-foreground">Entidad genérica</span>
                      </div>
                    </SelectItem>
                  </SelectContent>
                </Select>
                {errors.entity_code && (
                  <p className="text-sm text-destructive">{errors.entity_code}</p>
                )}
              </div>

              {/* Parent Workflow (for grouping) */}
              <div className="space-y-2">
                <Label htmlFor="parent_workflow_code">Workflow Padre (Agrupación)</Label>
                <Select
                  value={formData.parent_workflow_code || '_none'}
                  onValueChange={(value) =>
                    handleChange('parent_workflow_code', value === '_none' ? null : value)
                  }
                  disabled={loadingWorkflows}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={loadingWorkflows ? 'Cargando...' : 'Ninguno (es padre)'}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="_none">
                      <span className="text-muted-foreground">Ninguno (es workflow padre)</span>
                    </SelectItem>
                    {parentWorkflows.map((wf) => (
                      <SelectItem key={wf.code} value={wf.code}>
                        <div className="flex flex-col">
                          <span className="font-medium">{wf.name_es}</span>
                          <span className="text-xs text-muted-foreground font-mono">{wf.code}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Agrupe workflows bajo un padre para organización jerárquica
                </p>
              </div>

              {/* Is Parent */}
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="is_parent">Es workflow padre</Label>
                  <p className="text-xs text-muted-foreground">
                    Los workflows padre actúan como grupos para otros workflows
                  </p>
                </div>
                <Switch
                  id="is_parent"
                  checked={formData.is_parent || false}
                  onCheckedChange={(checked) => {
                    handleChange('is_parent', checked)
                    if (checked) {
                      handleChange('parent_workflow_code', null)
                    }
                  }}
                  disabled={!!formData.parent_workflow_code}
                />
              </div>

              {/* Tags */}
              <div className="space-y-2">
                <Label>Etiquetas</Label>
                <div className="flex gap-2">
                  <Input
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    placeholder="Añadir etiqueta..."
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addTag()
                      }
                    }}
                  />
                  <Button type="button" variant="outline" size="icon" onClick={addTag}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {formData.tags && formData.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {formData.tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="gap-1">
                        <Tag className="h-3 w-3" />
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeTag(tag)}
                          className="ml-1 hover:text-destructive"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Workflow Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" />
                Configuración
              </CardTitle>
              <CardDescription>Tipo de workflow y opciones</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Workflow Type */}
              <div className="space-y-2">
                <Label htmlFor="workflow_type">Tipo de Workflow</Label>
                <Select
                  value={formData.workflow_type}
                  onValueChange={(value) => handleChange('workflow_type', value as WorkflowType)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Seleccionar tipo" />
                  </SelectTrigger>
                  <SelectContent>
                    {WORKFLOW_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Agent Validation */}
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="requires_agent_validation">Requiere validación de agente</Label>
                  <p className="text-xs text-muted-foreground">
                    Un agente debe revisar y aprobar la solicitud
                  </p>
                </div>
                <Switch
                  id="requires_agent_validation"
                  checked={formData.requires_agent_validation}
                  onCheckedChange={(checked) => handleChange('requires_agent_validation', checked)}
                />
              </div>

              {/* Appointment */}
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="requires_appointment">Requiere cita</Label>
                  <p className="text-xs text-muted-foreground">
                    El ciudadano debe agendar una cita presencial
                  </p>
                </div>
                <Switch
                  id="requires_appointment"
                  checked={formData.requires_appointment}
                  onCheckedChange={(checked) => handleChange('requires_appointment', checked)}
                />
              </div>

              {/* Is Active */}
              <div className="flex items-center justify-between rounded-lg border p-4">
                <div className="space-y-0.5">
                  <Label htmlFor="is_active">Activo</Label>
                  <p className="text-xs text-muted-foreground">
                    Disponible para nuevas solicitudes
                  </p>
                </div>
                <Switch
                  id="is_active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => handleChange('is_active', checked)}
                />
              </div>
            </CardContent>
          </Card>

          {/* SLA & Display */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" />
                SLA y Visualización
              </CardTitle>
              <CardDescription>Tiempos de procesamiento y orden de visualización</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* SLA Hours */}
              <div className="space-y-2">
                <Label htmlFor="sla_hours">SLA (horas)</Label>
                <Input
                  id="sla_hours"
                  type="number"
                  min={1}
                  value={formData.sla_hours}
                  onChange={(e) => handleChange('sla_hours', parseInt(e.target.value) || 48)}
                  className={cn(errors.sla_hours && 'border-destructive')}
                />
                <p className="text-xs text-muted-foreground">
                  Tiempo máximo de procesamiento en horas hábiles
                </p>
                {errors.sla_hours && (
                  <p className="text-sm text-destructive">{errors.sla_hours}</p>
                )}
              </div>

              {/* Display Order */}
              <div className="space-y-2">
                <Label htmlFor="display_order">Orden de visualización</Label>
                <Input
                  id="display_order"
                  type="number"
                  min={0}
                  value={formData.display_order}
                  onChange={(e) => handleChange('display_order', parseInt(e.target.value) || 0)}
                />
                <p className="text-xs text-muted-foreground">
                  Número menor = aparece primero en listas
                </p>
              </div>

              {/* Max Processing Days */}
              <div className="space-y-2">
                <Label htmlFor="max_processing_days">Días máximos de procesamiento</Label>
                <Input
                  id="max_processing_days"
                  type="number"
                  min={1}
                  max={365}
                  value={formData.max_processing_days ?? ''}
                  onChange={(e) => handleChange('max_processing_days', e.target.value ? parseInt(e.target.value) : null)}
                />
                <p className="text-xs text-muted-foreground">
                  Días hábiles máximos para completar el trámite (opcional)
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Submit Buttons */}
        <div className="flex justify-end gap-4 mt-6">
          <Button type="button" variant="outline" onClick={handleBack}>
            {tCommon('cancel')}
          </Button>
          <Button type="submit" disabled={createWorkflowMutation.isPending || isLoading}>
            {createWorkflowMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Creando...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Crear Workflow
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
