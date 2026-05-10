'use client';

/**
 * Create New Role Page - Wizard Style
 * Step-by-step wizard for creating a custom role with permissions
 *
 * @module dashboard/admin/roles/new
 * @date 2025-01-16
 */

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  Shield,
  ArrowLeft,
  ArrowRight,
  Loader2,
  Key,
  Search,
  AlertCircle,
  Check,
  Building2,
  Users,
  AlertTriangle,
  CheckCircle2,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';

import { useCreateRole, rolesApi } from '@/modules/roles-admin';
import type { CreateRoleRequest } from '@/modules/roles-admin';
import { usePermissions, useModuleNames } from '@/modules/permissions-admin';
import type { Permission } from '@/modules/permissions-admin';

// Role templates based on existing profiles
interface RoleTemplate {
  id: string
  icon: React.ComponentType<{ className?: string }>
  sourceRoleCode: string // Existing role to copy permissions from
  defaultEntityType: string | null
  defaultCodePrefix: string
}

const ROLE_TEMPLATES: RoleTemplate[] = [
  {
    id: 'agent',
    icon: Users,
    sourceRoleCode: 'agent_cnedoge_pasaporte', // 24 perms base agent
    defaultEntityType: 'agent',
    defaultCodePrefix: 'agent_',
  },
  {
    id: 'supervisor',
    icon: Shield,
    sourceRoleCode: 'supervisor_cnedoge_pasaporte', // 21 perms base supervisor
    defaultEntityType: 'entity_agent',
    defaultCodePrefix: 'supervisor_',
  },
  {
    id: 'admin_module',
    icon: Key,
    sourceRoleCode: 'admin_security', // 28 perms scoped admin
    defaultEntityType: null,
    defaultCodePrefix: 'admin_',
  },
  {
    id: 'custom',
    icon: FileText,
    sourceRoleCode: '', // No template
    defaultEntityType: null,
    defaultCodePrefix: '',
  },
];

export default function CreateRolePage() {
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('admin.roles');

  // Step definitions using i18n
  const STEPS = useMemo(() => [
    { id: 0, title: t('stepTemplate'), description: t('stepTemplateDesc'), icon: Shield },
    { id: 1, title: t('stepInfoLabel'), description: t('stepInfoDesc'), icon: FileText },
    { id: 2, title: t('stepPermissionsLabel'), description: t('stepPermissionsDesc'), icon: Key },
    { id: 3, title: t('stepConfirmationLabel'), description: t('stepConfirmationDesc'), icon: CheckCircle2 },
  ], [t]);

  // Wizard state
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [templateLoading, setTemplateLoading] = useState(false);

  // Form state
  const [formData, setFormData] = useState<CreateRoleRequest>({
    name: '',
    code: '',
    entity_type: null,
    description: '',
  });
  const [selectedPermissions, setSelectedPermissions] = useState<string[]>([]);
  const [permissionSearch, setPermissionSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<string>('all');
  const [expandedModules, setExpandedModules] = useState<string[]>([]);

  const createMutation = useCreateRole();

  // Fetch permissions for selection
  const { data: permissions = [], isLoading: permissionsLoading } = usePermissions({
    module_name: moduleFilter === 'all' ? undefined : moduleFilter,
  });

  const modules = useModuleNames();

  // Filter permissions by search
  const filteredPermissions = useMemo(() => {
    if (!permissionSearch) return permissions;
    const query = permissionSearch.toLowerCase();
    return permissions.filter(
      (perm) =>
        perm.name.toLowerCase().includes(query) ||
        perm.description?.toLowerCase().includes(query) ||
        perm.resource.toLowerCase().includes(query)
    );
  }, [permissions, permissionSearch]);

  // Group permissions by module
  const groupedPermissions = useMemo(() => {
    return filteredPermissions.reduce((acc, perm) => {
      const module = perm.module_name || 'other';
      if (!acc[module]) acc[module] = [];
      acc[module].push(perm);
      return acc;
    }, {} as Record<string, Permission[]>);
  }, [filteredPermissions]);

  // Selected permissions details
  const selectedPermissionsDetails = useMemo(() => {
    return permissions.filter((p) => selectedPermissions.includes(p.id));
  }, [permissions, selectedPermissions]);

  // Template selection handler
  const handleSelectTemplate = async (templateId: string) => {
    setSelectedTemplate(templateId);
    const template = ROLE_TEMPLATES.find((tpl) => tpl.id === templateId);
    if (!template) return;

    // Pre-fill form defaults
    setFormData((prev) => ({
      ...prev,
      entity_type: template.defaultEntityType,
      code: template.defaultCodePrefix,
    }));

    // Load permissions from source role
    if (template.sourceRoleCode) {
      setTemplateLoading(true);
      try {
        const sourceRole = await rolesApi.getByCode(template.sourceRoleCode);
        const permIds = await rolesApi.getPermissions(sourceRole.id);
        setSelectedPermissions(permIds);
      } catch (err) {
        console.error('Failed to load template permissions:', err);
        // Non-blocking: user can still manually select permissions
      } finally {
        setTemplateLoading(false);
      }
    } else {
      setSelectedPermissions([]);
    }

    setCurrentStep(1);
  };

  // Validation for each step
  const isStep0Valid = selectedTemplate !== null;
  const isStep1Valid = formData.name.trim().length >= 2 && formData.code.trim().length >= 2;
  const isStep2Valid = true; // Permissions are optional
  const canProceed = currentStep === 0 ? isStep0Valid : currentStep === 1 ? isStep1Valid : currentStep === 2 ? isStep2Valid : true;

  const handleCodeChange = (value: string) => {
    const formatted = value.toLowerCase().replace(/[^a-z0-9_]/g, '_');
    setFormData({ ...formData, code: formatted });
  };

  const togglePermission = (permissionId: string) => {
    setSelectedPermissions((prev) =>
      prev.includes(permissionId)
        ? prev.filter((id) => id !== permissionId)
        : [...prev, permissionId]
    );
  };

  const toggleModule = (module: string, perms: Permission[]) => {
    const modulePermIds = perms.map((p) => p.id);
    const allSelected = modulePermIds.every((id) => selectedPermissions.includes(id));

    if (allSelected) {
      setSelectedPermissions((prev) => prev.filter((id) => !modulePermIds.includes(id)));
    } else {
      setSelectedPermissions((prev) => {
        const combined = [...prev, ...modulePermIds];
        return combined.filter((id, index) => combined.indexOf(id) === index);
      });
    }
  };

  const handleSubmit = async () => {
    if (!formData.name.trim() || !formData.code.trim()) {
      toast.error(t('nameCodeRequired'));
      return;
    }

    try {
      // Step 1: Create the role
      const newRole = await createMutation.mutateAsync(formData);

      // Step 2: Assign permissions if any selected
      if (selectedPermissions.length > 0) {
        try {
          await rolesApi.assignPermissions(newRole.id, {
            permission_ids: selectedPermissions,
            granted: true,
          });
          toast.success(
            t('roleCreatedWithPerms', { count: selectedPermissions.length }),
            { description: t('roleCreatedWithPermsDesc', { name: formData.name }) }
          );
        } catch (permErr) {
          // Role created but permissions failed
          toast.warning(
            t('roleCreatedPermsError'),
            { description: t('roleCreatedPermsErrorDesc') }
          );
          console.error('Permission assignment error:', permErr);
        }
      } else {
        toast.success(t('createSuccess'));
      }

      router.push(`/${locale}/dashboard/admin/roles/${newRole.id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('createError'));
    }
  };

  const nextStep = () => {
    if (currentStep < 3 && canProceed) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const prevStep = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const getEntityTypeLabel = (entityType: string | null | undefined) => {
    if (entityType === 'entity_agent' || entityType === 'agent') return t('entityTypeValue_agent');
    return t('entityTypeValue_global');
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/admin/roles`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-3">
            <Shield className="h-7 w-7" />
            {t('createRoleTitle')}
          </h1>
          <p className="text-muted-foreground mt-1">
            {t('createRoleSubtitle')}
          </p>
        </div>
      </div>

      {/* Stepper */}
      <div className="flex items-center justify-center">
        <div className="flex items-center gap-2">
          {STEPS.map((step, index) => {
            const StepIcon = step.icon;
            const isActive = currentStep === step.id;
            const isCompleted = currentStep > step.id;

            return (
              <div key={step.id} className="flex items-center">
                <button
                  onClick={() => isCompleted && setCurrentStep(step.id)}
                  disabled={!isCompleted && !isActive}
                  className={`flex items-center gap-3 px-4 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : isCompleted
                      ? 'bg-primary/10 text-primary cursor-pointer hover:bg-primary/20'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  <div
                    className={`flex items-center justify-center w-8 h-8 rounded-full ${
                      isActive
                        ? 'bg-primary-foreground/20'
                        : isCompleted
                        ? 'bg-primary/20'
                        : 'bg-muted-foreground/20'
                    }`}
                  >
                    {isCompleted ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <StepIcon className="h-4 w-4" />
                    )}
                  </div>
                  <div className="text-left hidden sm:block">
                    <div className="text-sm font-medium">{step.title}</div>
                    <div className="text-xs opacity-80">{step.description}</div>
                  </div>
                </button>
                {index < STEPS.length - 1 && (
                  <div
                    className={`w-8 h-0.5 mx-2 ${
                      currentStep > step.id ? 'bg-primary' : 'bg-muted'
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Step Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2">
          {/* Step 0: Template Selection */}
          {currentStep === 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  {t('templateSelection')}
                </CardTitle>
                <CardDescription>
                  {t('templateDescription')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid sm:grid-cols-2 gap-4">
                  {ROLE_TEMPLATES.map((template) => {
                    const TemplateIcon = template.icon;
                    const isSelected = selectedTemplate === template.id;

                    return (
                      <button
                        key={template.id}
                        onClick={() => handleSelectTemplate(template.id)}
                        disabled={templateLoading}
                        className={`flex flex-col items-start gap-3 p-5 rounded-lg border-2 text-left transition-all hover:shadow-md ${
                          isSelected
                            ? 'border-primary bg-primary/5'
                            : 'border-muted hover:border-primary/30'
                        }`}
                      >
                        <div className={`p-3 rounded-lg ${
                          isSelected ? 'bg-primary/10' : 'bg-muted'
                        }`}>
                          <TemplateIcon className={`h-6 w-6 ${
                            isSelected ? 'text-primary' : 'text-muted-foreground'
                          }`} />
                        </div>
                        <div>
                          <div className="font-semibold text-base">
                            {t(`template_${template.id}`)}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {t(`template_${template.id}_desc`)}
                          </p>
                        </div>
                        {template.sourceRoleCode && (
                          <Badge variant="secondary" className="text-xs">
                            {template.sourceRoleCode}
                          </Badge>
                        )}
                      </button>
                    );
                  })}
                </div>
                {templateLoading && (
                  <div className="flex items-center justify-center mt-4 gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm">{t('loadingTemplate')}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Step 1: Basic Info */}
          {currentStep === 1 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {t('roleInfoTitle')}
                </CardTitle>
                <CardDescription>
                  {t('roleInfoSubtitle')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Name */}
                <div className="grid gap-2">
                  <Label htmlFor="name" className="flex items-center gap-1">
                    {t('roleName')} <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder={t('roleNamePlaceholder')}
                    className="text-lg"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('roleNameHelp')}
                  </p>
                </div>

                {/* Code */}
                <div className="grid gap-2">
                  <Label htmlFor="code" className="flex items-center gap-1">
                    {t('codeLabel')} <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="code"
                    value={formData.code}
                    onChange={(e) => handleCodeChange(e.target.value)}
                    placeholder={t('codePlaceholder')}
                    className="font-mono"
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('codeHelp')}
                  </p>
                </div>

                {/* Entity Type */}
                <div className="grid gap-2">
                  <Label htmlFor="entity_type">{t('entityTypeLabel')}</Label>
                  <Select
                    value={formData.entity_type || 'none'}
                    onValueChange={(value) =>
                      setFormData({ ...formData, entity_type: value === 'none' ? null : value })
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder={t('entityTypePlaceholder')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">
                        <div className="flex items-center gap-2">
                          <Users className="h-4 w-4 text-muted-foreground" />
                          {t('entityTypeGlobal')}
                        </div>
                      </SelectItem>
                      <SelectItem value="agent">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-blue-500" />
                          {t('entityTypeAgent')}
                        </div>
                      </SelectItem>
                      <SelectItem value="entity_agent">
                        <div className="flex items-center gap-2">
                          <Building2 className="h-4 w-4 text-green-500" />
                          {t('entityTypeAgent')}
                        </div>
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {t('entityTypeHelp')}
                  </p>
                </div>

                {/* Description */}
                <div className="grid gap-2">
                  <Label htmlFor="description">{t('descriptionLabel')}</Label>
                  <Textarea
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder={t('descriptionPlaceholder')}
                    rows={4}
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {/* Step 2: Permissions Selection */}
          {currentStep === 2 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Key className="h-5 w-5" />
                  {t('permissionsTitle')}
                </CardTitle>
                <CardDescription>
                  {t('permissionsSubtitle', { count: selectedPermissions.length })}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Filters */}
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('searchPermission')}
                      value={permissionSearch}
                      onChange={(e) => setPermissionSearch(e.target.value)}
                      className="pl-9"
                    />
                  </div>
                  <Select value={moduleFilter} onValueChange={setModuleFilter}>
                    <SelectTrigger className="w-full sm:w-[200px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allModules')}</SelectItem>
                      <Separator className="my-1" />
                      {modules.map(
                        (mod: string | null) =>
                          mod && (
                            <SelectItem key={mod} value={mod}>
                              {mod}
                            </SelectItem>
                          )
                      )}
                    </SelectContent>
                  </Select>
                </div>

                {/* Quick Actions */}
                <div className="flex items-center justify-between py-2 px-3 bg-muted/50 rounded-lg">
                  <span className="text-sm text-muted-foreground">
                    {t('permissionsAvailable', { count: filteredPermissions.length })}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedPermissions(filteredPermissions.map((p) => p.id))}
                    >
                      {t('selectAll')}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedPermissions([])}
                      disabled={selectedPermissions.length === 0}
                    >
                      {t('deselectAll')}
                    </Button>
                  </div>
                </div>

                {/* Permissions List by Module */}
                <ScrollArea className="h-[400px] border rounded-lg">
                  {permissionsLoading ? (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : Object.keys(groupedPermissions).length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <AlertCircle className="h-8 w-8 mb-2" />
                      <p>{t('noPermissionsFound')}</p>
                    </div>
                  ) : (
                    <Accordion
                      type="multiple"
                      value={expandedModules}
                      onValueChange={setExpandedModules}
                      className="w-full"
                    >
                      {Object.entries(groupedPermissions)
                        .sort(([a], [b]) => a.localeCompare(b))
                        .map(([module, perms]) => {
                          const selectedInModule = perms.filter((p) =>
                            selectedPermissions.includes(p.id)
                          ).length;
                          const allSelected = selectedInModule === perms.length;
                          const someSelected = selectedInModule > 0 && !allSelected;

                          return (
                            <AccordionItem key={module} value={module} className="border-b-0">
                              <div className="flex items-center gap-2 pr-2">
                                <Checkbox
                                  checked={allSelected}
                                  onCheckedChange={() => toggleModule(module, perms)}
                                  className={someSelected ? 'opacity-60' : ''}
                                />
                                <AccordionTrigger className="flex-1 hover:no-underline py-3">
                                  <div className="flex items-center gap-3">
                                    <Badge variant="outline" className="capitalize font-mono">
                                      {module}
                                    </Badge>
                                    <span className="text-sm text-muted-foreground">
                                      {selectedInModule}/{perms.length}
                                    </span>
                                    {perms.some((p) => p.is_critical) && (
                                      <Badge
                                        variant="secondary"
                                        className="gap-1 bg-amber-100 text-amber-700 text-xs"
                                      >
                                        <AlertTriangle className="h-3 w-3" />
                                        {perms.filter((p) => p.is_critical).length}
                                      </Badge>
                                    )}
                                  </div>
                                </AccordionTrigger>
                              </div>
                              <AccordionContent className="pb-3 pt-0">
                                <div className="space-y-1 ml-6">
                                  {perms.map((perm) => (
                                    <div
                                      key={perm.id}
                                      onClick={() => togglePermission(perm.id)}
                                      className={`flex items-start gap-3 p-2 rounded-md cursor-pointer transition-colors ${
                                        selectedPermissions.includes(perm.id)
                                          ? 'bg-primary/10'
                                          : 'hover:bg-muted/50'
                                      }`}
                                    >
                                      <Checkbox
                                        checked={selectedPermissions.includes(perm.id)}
                                        onCheckedChange={() => togglePermission(perm.id)}
                                        className="mt-0.5"
                                      />
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <span className="font-medium text-sm">
                                            {perm.description || perm.name}
                                          </span>
                                          {perm.is_critical && (
                                            <Badge
                                              variant="secondary"
                                              className="text-xs bg-amber-100 text-amber-700"
                                            >
                                              {t('criticalLabel')}
                                            </Badge>
                                          )}
                                        </div>
                                        <code className="text-xs text-muted-foreground">
                                          {perm.name}
                                        </code>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              </AccordionContent>
                            </AccordionItem>
                          );
                        })}
                    </Accordion>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          )}

          {/* Step 3: Confirmation */}
          {currentStep === 3 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  {t('confirmationTitle')}
                </CardTitle>
                <CardDescription>
                  {t('confirmationSubtitle')}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Role Summary */}
                <div className="space-y-4">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    {t('roleInfoTitle')}
                  </h3>
                  <div className="grid gap-3 p-4 bg-muted/50 rounded-lg">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('nameLabel')}</span>
                      <span className="font-medium">{formData.name}</span>
                    </div>
                    <Separator />
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('codeLabel')}</span>
                      <code className="bg-muted px-2 py-0.5 rounded text-sm">{formData.code}</code>
                    </div>
                    <Separator />
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">{t('entityTypeLabel')}</span>
                      <Badge variant="outline">
                        {getEntityTypeLabel(formData.entity_type)}
                      </Badge>
                    </div>
                    {formData.description && (
                      <>
                        <Separator />
                        <div className="space-y-1">
                          <span className="text-muted-foreground text-sm">{t('descriptionLabel')}</span>
                          <p className="text-sm">{formData.description}</p>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {/* Permissions Summary */}
                <div className="space-y-4">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Key className="h-4 w-4" />
                    {t('permissionsCount')} ({selectedPermissions.length})
                  </h3>
                  {selectedPermissions.length === 0 ? (
                    <div className="p-4 bg-muted/50 rounded-lg text-center text-muted-foreground">
                      <AlertCircle className="h-6 w-6 mx-auto mb-2" />
                      <p>{t('noPermissionsSelected')}</p>
                      <p className="text-xs mt-1">
                        {t('noPermissionsSelectedHelp')}
                      </p>
                    </div>
                  ) : (
                    <ScrollArea className="h-[200px] p-4 bg-muted/50 rounded-lg">
                      <div className="flex flex-wrap gap-2">
                        {selectedPermissionsDetails.map((perm) => (
                          <Badge
                            key={perm.id}
                            variant={perm.is_critical ? 'default' : 'secondary'}
                            className={`${perm.is_critical ? 'bg-amber-100 text-amber-700' : ''}`}
                          >
                            {perm.description || perm.name}
                          </Badge>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </div>

                {/* Warning */}
                {selectedPermissionsDetails.some((p) => p.is_critical) && (
                  <div className="flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                    <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">{t('criticalWarningTitle')}</p>
                      <p className="text-sm text-amber-700 mt-1">
                        {t('criticalWarningDesc', { count: selectedPermissionsDetails.filter((p) => p.is_critical).length })}
                      </p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar Summary */}
        <div className="lg:col-span-1">
          <Card className="sticky top-6">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('summaryTitle')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Role Info */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <Shield className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium truncate">{formData.name || t('newRole')}</span>
                </div>
                {formData.code && (
                  <code className="text-xs bg-muted px-2 py-1 rounded block truncate">
                    {formData.code}
                  </code>
                )}
              </div>

              <Separator />

              {/* Entity Type */}
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Type</span>
                <Badge variant="outline" className="text-xs">
                  {getEntityTypeLabel(formData.entity_type)}
                </Badge>
              </div>

              <Separator />

              {/* Permissions Count */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t('permissionsCount')}</span>
                  <Badge variant={selectedPermissions.length > 0 ? 'default' : 'secondary'}>
                    {selectedPermissions.length}
                  </Badge>
                </div>
                {selectedPermissions.length > 0 && (
                  <div className="text-xs text-muted-foreground">
                    {selectedPermissionsDetails.filter((p) => p.is_critical).length > 0 && (
                      <span className="text-amber-600">
                        {t('includingCritical', { count: selectedPermissionsDetails.filter((p) => p.is_critical).length })}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Selected Permissions Preview */}
              {selectedPermissions.length > 0 && currentStep !== 3 && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <span className="text-xs text-muted-foreground">{t('previewLabel')}</span>
                    <div className="flex flex-wrap gap-1">
                      {selectedPermissionsDetails.slice(0, 5).map((perm) => (
                        <Badge key={perm.id} variant="outline" className="text-xs">
                          {perm.resource}
                        </Badge>
                      ))}
                      {selectedPermissions.length > 5 && (
                        <Badge variant="secondary" className="text-xs">
                          +{selectedPermissions.length - 5}
                        </Badge>
                      )}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between pt-4 border-t">
        <Button variant="outline" onClick={prevStep} disabled={currentStep === 0}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('previous')}
        </Button>

        <div className="flex items-center gap-2">
          <Link href={`/${locale}/dashboard/admin/roles`}>
            <Button variant="ghost">{t('cancel')}</Button>
          </Link>

          {currentStep < 3 ? (
            <Button onClick={nextStep} disabled={!canProceed}>
              {t('next')}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={createMutation.isPending || !isStep1Valid}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Check className="mr-2 h-4 w-4" />
              {t('createRoleButton')}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
