'use client';

/**
 * Create Agent/Admin Page — Compact 2-column layout
 * Zero-scroll design: Account (left) + Organization & Role (right)
 * Schedule + Review inline at bottom.
 *
 * All text via i18n (useTranslations). No hardcoded strings.
 *
 * Query params:
 * - ?type=agent — Create agent with profile
 * - ?type=admin — Create admin user only
 *
 * @module dashboard/admin/agents/new
 */

import { useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useQuery } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Form } from '@/components/ui/form';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { ArrowLeft, Loader2, UserCog, Shield, AlertTriangle } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { useInviteAgent, useInviteAdmin, useValidateAgent } from '@/modules/agents-admin/hooks';
import { AgentType } from '@/modules/agents-admin/types';
import type { AgentValidationIssue } from '@/modules/agents-admin/types';
import { hierarchyApi } from '@/modules/fiscal-services/services/api';
import { useEntities } from '@/modules/cities/hooks';
import { rolesApi } from '@/modules/roles-admin/services/api';
import { useLocationsByEntity } from '@/modules/entity-locations/hooks';
import {
  AgentAccountFields,
  AgentOrganizationFields,
  AgentRoleFields,
  AgentCapabilitiesFields,
  AgentApprovalFields,
  AgentScheduleFields,
  AgentReviewSummary,
} from '@/modules/agents-admin/components/form-sections';

// =============================================================================
// VALIDATION SCHEMAS — messages from i18n (resolved at render time in Zod refine)
// =============================================================================

const adminSchema = z.object({
  email: z.string().email(),
  first_name: z.string().min(2).max(100),
  last_name: z.string().min(2).max(100),
  phone_number: z
    .string()
    .regex(/^(222|555|551|333)\d{6}$/)
    .optional()
    .or(z.literal('')),
  preferred_language: z.enum(['es', 'fr', 'en']).default('es'),
});

const agentSchema = z.object({
  // User info
  email: z.string().email(),
  first_name: z.string().min(2).max(100),
  last_name: z.string().min(2).max(100),
  phone_number: z
    .string()
    .regex(/^(222|555|551|333)\d{6}$/)
    .optional()
    .or(z.literal('')),
  preferred_language: z.enum(['es', 'fr', 'en']).default('es'),
  // Organization
  agent_type: z.nativeEnum(AgentType),
  ministry_id: z.coerce.number().int().positive().optional(),
  entity_id: z.string().uuid().optional().or(z.literal('')),
  entity_location_id: z.string().uuid().optional().nullable().or(z.literal('ALL_SITES')).or(z.literal('')),
  // Role
  is_supervisor: z.boolean().default(false),
  rbac_role_id: z.string().uuid(),
  // Capabilities
  can_escalate: z.boolean().default(true),
  can_assign_tasks: z.boolean().default(false),
  can_reassign: z.boolean().default(false),
  // Approval
  can_approve_unlimited: z.boolean().default(false),
  max_approval_amount: z.coerce.number().positive().optional(),
  // Schedule
  working_hours_start: z.string().optional(),
  working_hours_end: z.string().optional(),
  working_days: z.array(z.number()).default([1, 2, 3, 4, 5]),
});

type AdminFormData = z.infer<typeof adminSchema>;
type AgentFormData = z.infer<typeof agentSchema>;

// =============================================================================
// COMPONENT
// =============================================================================

export default function CreateAgentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const t = useTranslations('admin.agents');

  const type = searchParams.get('type') || 'agent';
  const isAdmin = type === 'admin';

  // --- Data fetching ---
  const { data: ministriesData, isLoading: isLoadingMinistries } = useQuery({
    queryKey: ['ministries', 'list'],
    queryFn: () => hierarchyApi.ministries.list('es'),
    staleTime: 5 * 60 * 1000,
  });

  const { data: entitiesData, isLoading: isLoadingEntities } = useEntities({ is_active: true });

  const { data: rbacRolesData, isLoading: isLoadingRbacRoles } = useQuery({
    queryKey: ['roles', 'agent-rbac'],
    queryFn: () => rolesApi.getAgentRbacRoles(),
    staleTime: 5 * 60 * 1000,
  });

  // --- Transform data ---
  const ministries = ministriesData?.map(m => ({ id: m.id, name: m.name_es || m.nameEs || '' })) || [];
  const entities = entitiesData?.items?.map(e => ({
    id: e.id,
    code: e.code,
    name: e.name,
    entity_type: e.entity_type,
    workflow_codes: e.workflow_codes || [],
  })) || [];
  const rbacRoles = rbacRolesData || [];

  // --- Mutations ---
  const inviteAgentMutation = useInviteAgent();
  const inviteAdminMutation = useInviteAdmin();
  const validateMutation = useValidateAgent();

  // --- Validation state ---
  const [validationErrors, setValidationErrors] = useState<AgentValidationIssue[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<AgentValidationIssue[]>([]);
  const [showWarningsDialog, setShowWarningsDialog] = useState(false);
  const [pendingSubmitData, setPendingSubmitData] = useState<AgentFormData | null>(null);

  // --- Forms ---
  const adminForm = useForm<AdminFormData>({
    resolver: zodResolver(adminSchema),
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      phone_number: '',
      preferred_language: 'es',
    },
  });

  const agentForm = useForm<AgentFormData>({
    resolver: zodResolver(agentSchema),
    defaultValues: {
      email: '',
      first_name: '',
      last_name: '',
      phone_number: '',
      preferred_language: 'es',
      agent_type: AgentType.MINISTRY_AGENT,
      is_supervisor: false,
      rbac_role_id: '',
      can_approve_unlimited: false,
      can_escalate: true,
      can_assign_tasks: false,
      can_reassign: false,
      working_hours_start: '08:00',
      working_hours_end: '17:00',
      working_days: [1, 2, 3, 4, 5],
    },
  });

  // --- Watchers ---
  const watchAgentType = agentForm.watch('agent_type');
  const watchEntityId = agentForm.watch('entity_id');
  const watchIsSupervisor = agentForm.watch('is_supervisor');

  const selectedEntity = entities.find(e => e.id === watchEntityId);
  const isPaymentEntity = selectedEntity && (!selectedEntity.workflow_codes || selectedEntity.workflow_codes.length === 0);

  const { data: entityLocations, isLoading: isLoadingLocations } = useLocationsByEntity(
    selectedEntity?.code || '',
    !!selectedEntity?.code && watchAgentType === AgentType.ENTITY_AGENT
  );

  const watchRbacRoleId = agentForm.watch('rbac_role_id');
  const selectedRole = rbacRoles.find(r => r.id === watchRbacRoleId);

  // --- Submit handlers ---
  const handleAdminSubmit = async (data: AdminFormData) => {
    try {
      const response = await inviteAdminMutation.mutateAsync({
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
        phone_number: data.phone_number || undefined,
        preferred_language: data.preferred_language,
      });

      toast({
        title: t('toast.invitationSent') || response.message,
        description: `${data.email}`,
      });
      router.push('/dashboard/admin/agents?tab=admins');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      toast({ variant: 'destructive', title: t('toast.error') || 'Error', description: message });
    }
  };

  const doInviteAgent = useCallback(async (data: AgentFormData) => {
    try {
      const capabilities = data.is_supervisor
        ? { can_escalate: data.can_escalate, can_assign_tasks: data.can_assign_tasks, can_reassign: data.can_reassign }
        : { can_escalate: true, can_assign_tasks: false, can_reassign: false };

      const response = await inviteAgentMutation.mutateAsync({
        user: {
          email: data.email,
          first_name: data.first_name,
          last_name: data.last_name,
          phone_number: data.phone_number || undefined,
          preferred_language: data.preferred_language,
        },
        agent_type: data.agent_type,
        is_supervisor: data.is_supervisor,
        ministry_id: data.agent_type === AgentType.MINISTRY_AGENT ? data.ministry_id : undefined,
        entity_id: data.agent_type === AgentType.ENTITY_AGENT ? data.entity_id : undefined,
        entity_location_id:
          data.agent_type === AgentType.ENTITY_AGENT &&
          data.entity_location_id &&
          data.entity_location_id !== 'ALL_SITES'
            ? data.entity_location_id
            : null,
        rbac_role_id: data.rbac_role_id,
        ...capabilities,
        can_approve_unlimited: data.can_approve_unlimited,
        max_approval_amount: data.can_approve_unlimited ? undefined : data.max_approval_amount,
        working_hours_start: data.working_hours_start,
        working_hours_end: data.working_hours_end,
        working_days: data.working_days,
      });

      toast({
        title: t('toast.invitationSent') || response.message,
        description: `${data.email}`,
      });
      router.push('/dashboard/admin/agents');
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      toast({ variant: 'destructive', title: t('toast.error') || 'Error', description: message });
    }
  }, [inviteAgentMutation, toast, router, t]);

  const handleAgentSubmit = async (data: AgentFormData) => {
    setValidationErrors([]);
    setValidationWarnings([]);

    try {
      const result = await validateMutation.mutateAsync({
        email: data.email,
        first_name: data.first_name,
        last_name: data.last_name,
        agent_type: data.agent_type,
        entity_id: data.entity_id || undefined,
        entity_location_id: data.entity_location_id || undefined,
        ministry_id: data.agent_type === AgentType.MINISTRY_AGENT ? data.ministry_id : undefined,
        is_supervisor: data.is_supervisor,
        rbac_role_id: data.rbac_role_id,
      });

      setValidationErrors(result.errors);
      setValidationWarnings(result.warnings);

      if (result.errors.length > 0) {
        toast({
          variant: 'destructive',
          title: t('sections.validationErrors', { count: result.errors.length }),
          description: result.errors[0].message,
        });
        return;
      }

      if (result.warnings.length > 0) {
        setPendingSubmitData(data);
        setShowWarningsDialog(true);
        return;
      }

      await doInviteAgent(data);
    } catch {
      await doInviteAgent(data);
    }
  };

  const handleConfirmWithWarnings = async () => {
    setShowWarningsDialog(false);
    if (pendingSubmitData) {
      await doInviteAgent(pendingSubmitData);
      setPendingSubmitData(null);
    }
  };

  const isLoading = inviteAgentMutation.isPending || inviteAdminMutation.isPending || validateMutation.isPending;

  // =========================================================================
  // RENDER — Admin form (simple single card)
  // =========================================================================
  if (isAdmin) {
    return (
      <div className="space-y-4">
        {/* Compact header with actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => router.back()}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
            <div className="flex items-center gap-2">
              <Shield className="h-6 w-6" />
              <h1 className="text-xl font-bold">{t('sections.createAdmin')}</h1>
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => router.back()}>
              {t('sections.cancel')}
            </Button>
            <Button size="sm" disabled={isLoading} onClick={adminForm.handleSubmit(handleAdminSubmit)}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('sections.sendInvitation')}
            </Button>
          </div>
        </div>

        <Form {...adminForm}>
          <form onSubmit={adminForm.handleSubmit(handleAdminSubmit)}>
            <Card>
              <CardHeader className="pb-4">
                <CardTitle className="text-base">{t('sections.accountInfo')}</CardTitle>
                <p className="text-sm text-muted-foreground">{t('sections.accountInfoAdminDesc')}</p>
              </CardHeader>
              <CardContent>
                <AgentAccountFields form={adminForm} />
              </CardContent>
            </Card>
          </form>
        </Form>
      </div>
    );
  }

  // =========================================================================
  // RENDER — Agent form (full-width stacked cards, compact inline fields)
  // =========================================================================
  return (
    <div className="space-y-4">
      {/* Compact header with inline actions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-2">
            <UserCog className="h-6 w-6" />
            <div>
              <h1 className="text-xl font-bold">{t('sections.createAgent')}</h1>
              <p className="text-xs text-muted-foreground">{t('sections.createAgentDesc')}</p>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => router.back()}>
            {t('sections.cancel')}
          </Button>
          <Button size="sm" disabled={isLoading} onClick={agentForm.handleSubmit(handleAgentSubmit)}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t('sections.sendInvitation')}
          </Button>
        </div>
      </div>

      <Form {...agentForm}>
        <form onSubmit={agentForm.handleSubmit(handleAgentSubmit)} className="space-y-4">
          {/* === Account Info — full width === */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('sections.accountInfo')}</CardTitle>
              <p className="text-xs text-muted-foreground">{t('sections.accountInfoDesc')}</p>
            </CardHeader>
            <CardContent>
              <AgentAccountFields form={agentForm} />
            </CardContent>
          </Card>

          {/* === Organization — full width, inline fields === */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('sections.organization')}</CardTitle>
              <p className="text-xs text-muted-foreground">{t('sections.organizationDesc')}</p>
            </CardHeader>
            <CardContent>
              <AgentOrganizationFields
                form={agentForm}
                ministries={ministries}
                entities={entities}
                entityLocations={entityLocations}
                isLoadingMinistries={isLoadingMinistries}
                isLoadingEntities={isLoadingEntities}
                isLoadingLocations={isLoadingLocations}
                inline
              />
            </CardContent>
          </Card>

          {/* === Role & Permissions — full width, inline fields === */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('sections.rolePermissions')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <AgentRoleFields
                form={agentForm}
                rbacRoles={rbacRoles}
                isLoadingRoles={isLoadingRbacRoles}
                inline
              />

              {/* Capabilities — supervisor only */}
              {watchIsSupervisor && (
                <>
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium mb-3">{t('sections.supervisorCapabilities')}</h4>
                    <AgentCapabilitiesFields form={agentForm} />
                  </div>
                </>
              )}

              {/* Approval — payment entities only */}
              {isPaymentEntity && (
                <>
                  <Separator />
                  <div>
                    <h4 className="text-sm font-medium mb-3">{t('sections.approvalLimits')}</h4>
                    <AgentApprovalFields form={agentForm} />
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* === Bottom row: Schedule + Review Summary side by side === */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('sections.schedule')}</CardTitle>
              </CardHeader>
              <CardContent>
                <AgentScheduleFields form={agentForm} />
              </CardContent>
            </Card>

            <AgentReviewSummary
              form={agentForm}
              entityName={selectedEntity?.name}
              roleName={selectedRole ? `${selectedRole.name} (${selectedRole.code})` : undefined}
              validationErrors={validationErrors}
              validationWarnings={validationWarnings}
              forceOpen={validationErrors.length > 0 || validationWarnings.length > 0}
            />
          </div>
        </form>
      </Form>

      {/* Warnings Confirmation Dialog */}
      <AlertDialog open={showWarningsDialog} onOpenChange={setShowWarningsDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-orange-500" />
              {t('sections.warningsTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3">
                <p>{t('sections.warningsDetected', { count: validationWarnings.length })}</p>
                <ul className="space-y-1.5">
                  {validationWarnings.map((w, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-orange-700">
                      <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
                      <span><strong>{w.field}</strong>: {w.message}</span>
                    </li>
                  ))}
                </ul>
                <p className="text-sm">{t('sections.warningsContinue')}</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('sections.warningsCorrect')}</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmWithWarnings}>
              {t('sections.warningsContinueAnyway')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
