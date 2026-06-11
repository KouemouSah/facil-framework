'use client'

/**
 * Create Email Template Page
 * Page for creating new email templates with inline form
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import { ArrowLeft, RefreshCw, FileText, Check, Copy, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { RichTextEditor } from '@/modules/communications/components/RichTextEditor'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useToast } from '@/hooks/use-toast'
import { useCreateEmailTemplate } from '@/modules/communications/hooks/useEmailTemplates'
import { STARTER_TEMPLATES, type StarterTemplate } from '@/modules/communications/components/EmailTemplateStarters'
import { VARIABLE_GROUPS, getAllPredefinedVariables } from '@/modules/communications/components/EmailTemplateVariables'
import type { EmailTemplateCreate, TemplateVariable } from '@/modules/communications/types'
import { cn } from '@/core/utils'

// Extract variables from HTML content (finds all {{variable_name}} patterns)
function extractVariablesFromHtml(html: string): string[] {
  const regex = /\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}/g
  const matches: string[] = []
  let match
  while ((match = regex.exec(html)) !== null) {
    if (!matches.includes(match[1])) {
      matches.push(match[1])
    }
  }
  return matches
}

// Get TemplateVariable objects from variable names
function getVariablesFromNames(names: string[]): TemplateVariable[] {
  const allVariables = getAllPredefinedVariables()
  return names.map(name => {
    const predefined = allVariables.find(v => v.name === name)
    if (predefined) {
      return predefined
    }
    // Custom variable (not predefined)
    return {
      name,
      description: 'Custom variable',
      required: false,
    }
  })
}

const EMAIL_CATEGORY_KEYS = ['auth', 'notifications', 'payments', 'declarations', 'reminders', 'alerts', 'system'] as const

export default function NewEmailTemplatePage() {
  const locale = useLocale()
  const router = useRouter()
  const searchParams = useSearchParams()
  const t = useTranslations('admin.emailTemplates')
  const tCommon = useTranslations('common')
  const { toast } = useToast()
  const { mutateAsync: createTemplate, isPending: isSubmitting } = useCreateEmailTemplate()

  const [formData, setFormData] = useState<EmailTemplateCreate>({
    templateCode: '',
    nameEs: '',
    nameFr: '',
    nameEn: '',
    subjectEs: '',
    subjectFr: '',
    subjectEn: '',
    descriptionEs: '',
    descriptionFr: '',
    descriptionEn: '',
    htmlContent: '',
    variables: [],
    category: 'notifications',
    isActive: true,
  })

  const [selectedStarterTemplate, setSelectedStarterTemplate] = useState<string | null>(null)
  const [copiedVariable, setCopiedVariable] = useState<string | null>(null)
  const [starterTemplatesExpanded, setStarterTemplatesExpanded] = useState(false)
  const [variablesExpanded, setVariablesExpanded] = useState(false)
  const [selectedVariableContext, setSelectedVariableContext] = useState<string>(VARIABLE_GROUPS[0]?.context || 'user')

  // Auto-detect variables from HTML content
  const detectedVariables = useMemo(() => {
    const variableNames = extractVariablesFromHtml(formData.htmlContent)
    return getVariablesFromNames(variableNames)
  }, [formData.htmlContent])

  // Get the selected variable group
  const selectedVariableGroup = useMemo(() => {
    return VARIABLE_GROUPS.find(g => g.context === selectedVariableContext) || VARIABLE_GROUPS[0]
  }, [selectedVariableContext])

  // Check for missing required variables
  const missingRequiredVariables = useMemo(() => {
    const allRequired = getAllPredefinedVariables().filter(v => v.required)
    const detectedNames = detectedVariables.map(v => v.name)
    // Only warn if user has started using variables from that context
    const usedContexts = new Set<string>()
    detectedVariables.forEach(v => {
      const group = VARIABLE_GROUPS.find(g => g.variables.some(gv => gv.name === v.name))
      if (group) usedContexts.add(group.context)
    })
    return allRequired.filter(v => {
      const group = VARIABLE_GROUPS.find(g => g.variables.some(gv => gv.name === v.name))
      return group && usedContexts.has(group.context) && !detectedNames.includes(v.name)
    })
  }, [detectedVariables])

  // Copy variable placeholder to clipboard
  const copyToClipboard = useCallback(async (variableName: string) => {
    const placeholder = `{{${variableName}}}`
    try {
      await navigator.clipboard.writeText(placeholder)
      setCopiedVariable(variableName)
      setTimeout(() => setCopiedVariable(null), 2000)
      toast({
        title: t('variableCopied') || 'Copied!',
        description: placeholder,
      })
    } catch {
      toast({
        variant: 'destructive',
        title: t('copyError') || 'Copy failed',
        description: t('copyErrorDescription') || 'Please copy manually',
      })
    }
  }, [toast, t])

  // Filter starter templates by selected category
  const filteredStarterTemplates = useMemo(() => {
    if (formData.category === 'notifications') {
      // Show all templates when default category is selected
      return STARTER_TEMPLATES
    }
    return STARTER_TEMPLATES.filter(t => t.category === formData.category)
  }, [formData.category])

  // Handle starter template from URL parameter
  useEffect(() => {
    const starterId = searchParams.get('starter')
    if (starterId) {
      const template = STARTER_TEMPLATES.find(t => t.id === starterId)
      if (template) {
        setSelectedStarterTemplate(template.id)
        setFormData(prev => ({
          ...prev,
          htmlContent: template.htmlContent,
          category: template.category,
        }))
      }
    }
  }, [searchParams])

  const handleSelectStarterTemplate = (template: StarterTemplate) => {
    setSelectedStarterTemplate(template.id)
    setFormData({
      ...formData,
      htmlContent: template.htmlContent,
      category: template.category,
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Auto-detect variables from content before submission
    const templateData: EmailTemplateCreate = {
      ...formData,
      variables: detectedVariables,
    }

    try {
      await createTemplate(templateData)
      toast({
        title: t('successTitle'),
        description: t('templateCreated'),
      })
      router.push(`/${locale}/dashboard/admin/communications/email-templates`)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: error instanceof Error ? error.message : t('errorCreating'),
      })
    }
  }

  const handleCancel = () => {
    router.back()
  }

  // Check if a variable is used in the current content
  const isVariableUsed = (name: string) => {
    return detectedVariables.some(v => v.name === name)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleCancel}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('createTitle')}</h1>
          <p className="text-muted-foreground mt-2">{t('createDescription')}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Information */}
        <Card>
          <CardHeader>
            <CardTitle>{t('basicInfo')}</CardTitle>
            <CardDescription>{t('basicInfoDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="templateCode">{t('fieldTemplateCode')} *</Label>
                <Input
                  id="templateCode"
                  value={formData.templateCode}
                  onChange={(e) => setFormData({ ...formData, templateCode: e.target.value.toUpperCase() })}
                  placeholder="WELCOME_EMAIL"
                  maxLength={100}
                  required
                />
                <p className="text-xs text-muted-foreground">{t('templateCodeHint')}</p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="category">{t('fieldCategory')}</Label>
                <Select
                  value={formData.category}
                  onValueChange={(v) => setFormData({ ...formData, category: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EMAIL_CATEGORY_KEYS.map((categoryKey) => (
                      <SelectItem key={categoryKey} value={categoryKey}>
                        {t(`categories.${categoryKey}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="nameEs">{t('fieldNameEs')} *</Label>
                <Input
                  id="nameEs"
                  value={formData.nameEs}
                  onChange={(e) => setFormData({ ...formData, nameEs: e.target.value })}
                  placeholder="Correo de Bienvenida"
                  maxLength={255}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nameFr">{t('fieldNameFr')}</Label>
                <Input
                  id="nameFr"
                  value={formData.nameFr}
                  onChange={(e) => setFormData({ ...formData, nameFr: e.target.value })}
                  placeholder="Email de Bienvenue"
                  maxLength={255}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="nameEn">{t('fieldNameEn')}</Label>
                <Input
                  id="nameEn"
                  value={formData.nameEn}
                  onChange={(e) => setFormData({ ...formData, nameEn: e.target.value })}
                  placeholder="Welcome Email"
                  maxLength={255}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Email Subjects */}
        <Card>
          <CardHeader>
            <CardTitle>{t('subjectTitle')}</CardTitle>
            <CardDescription>{t('subjectDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="subjectEs">{t('fieldSubjectEs')} *</Label>
                <Input
                  id="subjectEs"
                  value={formData.subjectEs}
                  onChange={(e) => setFormData({ ...formData, subjectEs: e.target.value })}
                  placeholder="Bienvenido a Facil"
                  maxLength={255}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="subjectFr">{t('fieldSubjectFr')}</Label>
                <Input
                  id="subjectFr"
                  value={formData.subjectFr}
                  onChange={(e) => setFormData({ ...formData, subjectFr: e.target.value })}
                  placeholder="Bienvenue à Facil"
                  maxLength={255}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="subjectEn">{t('fieldSubjectEn')}</Label>
                <Input
                  id="subjectEn"
                  value={formData.subjectEn}
                  onChange={(e) => setFormData({ ...formData, subjectEn: e.target.value })}
                  placeholder="Welcome to Facil"
                  maxLength={255}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Descriptions */}
        <Card>
          <CardHeader>
            <CardTitle>{t('descriptionTitle')}</CardTitle>
            <CardDescription>{t('descriptionHelp')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="descriptionEs">{t('fieldDescriptionEs')}</Label>
                <Textarea
                  id="descriptionEs"
                  value={formData.descriptionEs}
                  onChange={(e) => setFormData({ ...formData, descriptionEs: e.target.value })}
                  placeholder="Descripción de la plantilla..."
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="descriptionFr">{t('fieldDescriptionFr')}</Label>
                <Textarea
                  id="descriptionFr"
                  value={formData.descriptionFr}
                  onChange={(e) => setFormData({ ...formData, descriptionFr: e.target.value })}
                  placeholder="Description du modèle..."
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="descriptionEn">{t('fieldDescriptionEn')}</Label>
                <Textarea
                  id="descriptionEn"
                  value={formData.descriptionEn}
                  onChange={(e) => setFormData({ ...formData, descriptionEn: e.target.value })}
                  placeholder="Template description..."
                  rows={3}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Starter Templates - Collapsible */}
        <Card>
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setStarterTemplatesExpanded(!starterTemplatesExpanded)}
          >
            <div className="flex items-center gap-2">
              {starterTemplatesExpanded ? (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-5 h-5 text-muted-foreground" />
              )}
              <div>
                <CardTitle>{t('starterTemplates.title')}</CardTitle>
                <CardDescription className="mt-1">{t('starterTemplates.description')}</CardDescription>
              </div>
            </div>
          </CardHeader>
          {starterTemplatesExpanded && <CardContent>
            {filteredStarterTemplates.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>{t('noStarterTemplatesForCategory') || 'No starter templates for this category'}</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {filteredStarterTemplates.map((template) => (
                  <div
                    key={template.id}
                    onClick={() => handleSelectStarterTemplate(template)}
                    className={cn(
                      "relative cursor-pointer rounded-lg border-2 p-4 transition-all hover:border-primary hover:shadow-md",
                      selectedStarterTemplate === template.id
                        ? "border-primary bg-primary/5"
                        : "border-muted"
                    )}
                  >
                    {selectedStarterTemplate === template.id && (
                      <div className="absolute right-2 top-2">
                        <Check className="h-5 w-5 text-primary" />
                      </div>
                    )}
                    <div className="flex flex-col items-center text-center space-y-2">
                      <div className="rounded-full bg-muted p-3">
                        <FileText className="h-6 w-6 text-muted-foreground" />
                      </div>
                      <div>
                        <h4 className="font-medium text-sm">{template.name}</h4>
                        <p className="text-xs text-muted-foreground mt-1">
                          {template.description}
                        </p>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {t(`categories.${template.category}`)}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>}
        </Card>

        {/* HTML Content */}
        <Card>
          <CardHeader>
            <CardTitle>{t('htmlContentTitle')}</CardTitle>
            <CardDescription>{t('htmlContentDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t('fieldHtmlContent')} *</Label>
              <RichTextEditor
                content={formData.htmlContent}
                onChange={(html) => setFormData({ ...formData, htmlContent: html })}
                placeholder={t('htmlContentPlaceholder') || 'Start writing your email content...'}
              />
              <p className="text-xs text-muted-foreground">{t('htmlContentHint')}</p>
            </div>
          </CardContent>
        </Card>

        {/* Variables - Collapsible with Category Filter */}
        <Card>
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setVariablesExpanded(!variablesExpanded)}
          >
            <div className="flex items-center gap-2">
              {variablesExpanded ? (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronRight className="w-5 h-5 text-muted-foreground" />
              )}
              <div className="flex-1">
                <CardTitle>{t('variablesTitle')}</CardTitle>
                <CardDescription className="mt-1">
                  {t('variablesDescriptionNew') || 'Copy variables and paste them in your email content. They will be automatically detected.'}
                </CardDescription>
              </div>
              {detectedVariables.length > 0 && (
                <Badge variant="secondary" className="ml-2">
                  {detectedVariables.length} {t('inUse') || 'In Use'}
                </Badge>
              )}
            </div>
          </CardHeader>
          {variablesExpanded && <CardContent className="space-y-4">
            {/* Category Selector */}
            <div className="space-y-2">
              <Label>{t('selectVariableCategory') || 'Select Category'}</Label>
              <Select
                value={selectedVariableContext}
                onValueChange={setSelectedVariableContext}
              >
                <SelectTrigger className="w-full md:w-[300px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {VARIABLE_GROUPS.map((group) => (
                    <SelectItem key={group.context} value={group.context}>
                      <div className="flex items-center gap-2">
                        <span>{t(`variableGroups.${group.context}`)}</span>
                        <Badge variant="outline" className="ml-2 text-xs">
                          {group.variables.filter(v => isVariableUsed(v.name)).length}/{group.variables.length}
                        </Badge>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Selected Category Variables Table */}
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/50">
                    <TableHead>{t('variablePlaceholder') || 'Placeholder'}</TableHead>
                    <TableHead>{t('variableDescription') || 'Description'}</TableHead>
                    <TableHead className="w-[80px] text-center">{t('required') || 'Required'}</TableHead>
                    <TableHead className="w-[80px] text-center">{t('inUse') || 'In Use'}</TableHead>
                    <TableHead className="w-[80px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {selectedVariableGroup.variables.map((variable) => (
                    <TableRow
                      key={variable.name}
                      className={cn(
                        isVariableUsed(variable.name) && "bg-green-50 dark:bg-green-950/20"
                      )}
                    >
                      <TableCell>
                        <code className="text-sm font-mono bg-muted px-2 py-1 rounded">
                          {`{{${variable.name}}}`}
                        </code>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {variable.description}
                      </TableCell>
                      <TableCell className="text-center">
                        {variable.required ? (
                          <Badge variant="destructive" className="text-xs">
                            {tCommon('yes') || 'Yes'}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground text-sm">-</span>
                        )}
                      </TableCell>
                      <TableCell className="text-center">
                        {isVariableUsed(variable.name) ? (
                          <Check className="h-4 w-4 text-green-600 mx-auto" />
                        ) : (
                          <span className="text-muted-foreground text-sm">-</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => copyToClipboard(variable.name)}
                        >
                          {copiedVariable === variable.name ? (
                            <Check className="h-4 w-4 text-green-600" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Missing Required Variables Warning */}
            {missingRequiredVariables.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  {t('missingRequiredVariables') || 'Missing required variables:'}{' '}
                  {missingRequiredVariables.map(v => `{{${v.name}}}`).join(', ')}
                </AlertDescription>
              </Alert>
            )}

            {/* Detected Variables Summary */}
            {detectedVariables.length > 0 && (
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-green-600" />
                  {t('detectedVariables') || 'Detected Variables'} ({detectedVariables.length})
                </Label>
                <div className="flex flex-wrap gap-2">
                  {detectedVariables.map((variable) => (
                    <Badge
                      key={variable.name}
                      variant="secondary"
                      className="py-1.5"
                    >
                      <code className="text-xs">{`{{${variable.name}}}`}</code>
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>}
        </Card>

        {/* Settings */}
        <Card>
          <CardHeader>
            <CardTitle>{t('settingsTitle')}</CardTitle>
            <CardDescription>{t('settingsDescription')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <Switch
                id="isActive"
                checked={formData.isActive}
                onCheckedChange={(checked) => setFormData({ ...formData, isActive: checked })}
              />
              <Label htmlFor="isActive">{t('fieldActive')}</Label>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex items-center justify-end gap-4">
          <Button type="button" variant="outline" onClick={handleCancel} disabled={isSubmitting}>
            {tCommon('cancel')}
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <RefreshCw className="h-4 w-4 mr-2 animate-spin" />}
            {t('create')}
          </Button>
        </div>
      </form>
    </div>
  )
}
