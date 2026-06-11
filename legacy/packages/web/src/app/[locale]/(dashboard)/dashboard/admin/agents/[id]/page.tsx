'use client';

/**
 * Agent/Admin Detail Page (Refactored)
 * View and edit agent profile with context-adaptive form sections.
 *
 * Tabs: Profile | Activity
 *
 * @module dashboard/admin/agents/[id]
 */

import { useState, useEffect } from 'react';
import { useRouter, useParams, useSearchParams } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import * as z from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Form,
  FormField,
  FormItem,
  FormMessage,
} from '@/components/ui/form';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  ArrowLeft,
  Loader2,
  UserCog,
  Activity,
  XCircle,
  Settings,
  Power,
  PowerOff,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Save,
  AlertTriangle,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  useAgentProfile,
  useAgentNeighbors,
  useAgentWorkload,
  useAgentPerformance,
  useUpdateAgentProfile,
  useDeactivateAgent,
  useReactivateAgent,
} from '@/modules/agents-admin/hooks';
import { AgentActivityTab } from '@/modules/agents-admin/components';
import { adminUsersApi } from '@/modules/agents-admin/services/api';
import { AgentType } from '@/modules/agents-admin/types';
import type { AgentProfileUpdateRequest } from '@/modules/agents-admin/types';
import { hierarchyApi } from '@/modules/fiscal-services/services/api';
import { useEntities } from '@/modules/cities/hooks';
import { useRoles } from '@/modules/roles-admin/hooks/useRoles';
import { useLocationsByEntity } from '@/modules/entity-locations/hooks';
import {
  AgentOrganizationFields,
  AgentRoleFields,
  AgentCapabilitiesFields,
  AgentApprovalFields,
  AgentScheduleFields,
} from '@/modules/agents-admin/components/form-sections';

// =============================================================================
// VALIDATION SCHEMA
// =============================================================================

const profileSchema = z.object({
  agent_type: z.nativeEnum(AgentType),
  is_supervisor: z.boolean(),
  ministry_id: z.coerce.number().int().positive().optional().nullable(),
  entity_id: z.string().uuid().optional().nullable().or(z.literal('')),
  entity_location_id: z.string().uuid().optional().nullable().or(z.literal('ALL_SITES')).or(z.literal('')),
  rbac_role_id: z.string().uuid().optional().nullable().or(z.literal('')),
  can_approve_unlimited: z.boolean(),
  max_approval_amount: z.coerce.number().positive().optional().nullable(),
  can_escalate: z.boolean(),
  can_assign_tasks: z.boolean(),
  can_reassign: z.boolean(),
  working_hours_start: z.string().optional(),
  working_hours_end: z.string().optional(),
  working_days: z.array(z.number()).default([1, 2, 3, 4, 5]),
  is_active: z.boolean(),
  is_backup_agent: z.boolean(),
  specializations: z.array(z.string()).default([]),
});

type ProfileFormData = z.infer<typeof profileSchema>;

// =============================================================================
// COMPONENT
// =============================================================================

export default function AgentDetailPage() {
  // --- Data fetching ---
  const { data: ministriesData, isLoading: isLoadingMinistries } = useQuery({
    queryKey: ['ministries', 'list'],
    queryFn: () => hierarchyApi.ministries.list('es'),
    staleTime: 5 * 60 * 1000,
  });

  // Use full Entity (not EntitySimple) to get workflow_codes for context-adaptive UX
  const { data: entitiesData, isLoading: isLoadingEntities } = useEntities({ is_active: true });

  const { data: rolesData, isLoading: isLoadingRoles } = useRoles({ entity_type: null });

  // --- Transform data ---
  const ministries = ministriesData?.map(m => ({ id: m.id, name: m.name_es || m.nameEs || '' })) || [];
  const entities = entitiesData?.items?.map(e => ({
    id: e.id,
    code: e.code,
    name: e.name,
    entity_type: e.entity_type,
    workflow_codes: e.workflow_codes || [],
  })) || [];
  const rbacRoles = rolesData?.roles || [];

  const router = useRouter();
  const params = useParams();
  const locale = useLocale();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(searchParams.get('mode') === 'edit');
  const [deactivateReason, setDeactivateReason] = useState('');

  // Inline edit state for the info bar
  const [editingInfo, setEditingInfo] = useState(false);
  const [infoEmail, setInfoEmail] = useState('');
  const [infoPhone, setInfoPhone] = useState('');
  const [infoEntityId, setInfoEntityId] = useState('');
  const [infoLocationId, setInfoLocationId] = useState('');
  const [savingInfo, setSavingInfo] = useState(false);

  const profileId = params.id as string;

  // --- Queries ---
  const { data: profile, isLoading: profileLoading, error: profileError } = useAgentProfile(profileId);
  const { data: workload, isLoading: workloadLoading } = useAgentWorkload(profileId, !!profile);
  const { data: performance, isLoading: performanceLoading } = useAgentPerformance(profileId, !!profile);

  // Agent navigation — lightweight endpoint returns only prev/next IDs (no full list)
  const { data: neighbors, isLoading: neighborsLoading, error: neighborsError } = useAgentNeighbors(profileId, !!profile);
  const prevAgentId = neighbors?.prev_id ?? null;
  const nextAgentId = neighbors?.next_id ?? null;

  // --- Mutations ---
  const updateMutation = useUpdateAgentProfile();
  const deactivateMutation = useDeactivateAgent();
  const reactivateMutation = useReactivateAgent();

  // --- Form ---
  const form = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      agent_type: AgentType.MINISTRY_AGENT,
      is_supervisor: false,
      rbac_role_id: '',
      can_approve_unlimited: false,
      can_escalate: true,
      can_assign_tasks: false,
      can_reassign: false,
      is_active: true,
      is_backup_agent: false,
      specializations: [],
    },
  });

  // Update form when profile loads
  useEffect(() => {
    if (profile) {
      form.reset({
        agent_type: profile.agent_type,
        is_supervisor: profile.is_supervisor,
        ministry_id: profile.ministry_id ?? null,
        entity_id: profile.entity_id ?? '',
        entity_location_id: profile.entity_location_id ?? '',
        rbac_role_id: '',
        can_approve_unlimited: profile.can_approve_unlimited,
        max_approval_amount: profile.max_approval_amount ?? null,
        can_escalate: profile.can_escalate,
        can_assign_tasks: profile.can_assign_tasks,
        can_reassign: profile.can_reassign,
        working_hours_start: profile.working_hours_start ?? '08:00',
        working_hours_end: profile.working_hours_end ?? '17:00',
        working_days: profile.working_days ?? [1, 2, 3, 4, 5],
        is_active: profile.is_active,
        is_backup_agent: profile.is_backup_agent,
        specializations: profile.specializations ?? [],
      });
    }
  }, [profile, form]);

  // --- Watchers for context-adaptive visibility ---
  const watchAgentType = form.watch('agent_type');
  const watchEntityId = form.watch('entity_id');
  const watchIsSupervisor = form.watch('is_supervisor');

  // Derive entity info
  const selectedEntity = entities.find(e => e.id === watchEntityId);
  const selectedEntityCode = selectedEntity?.code;

  // Context-adaptive flags
  const isPaymentEntity = selectedEntity && (!selectedEntity.workflow_codes || selectedEntity.workflow_codes.length === 0);

  // Fetch locations for selected entity
  const { data: entityLocations, isLoading: isLoadingLocations } = useLocationsByEntity(
    selectedEntityCode || '',
    !!selectedEntityCode && watchAgentType === AgentType.ENTITY_AGENT
  );

  // Reset entity_location_id when entity changes (only after profile loaded)
  useEffect(() => {
    if (profile && watchEntityId !== profile.entity_id) {
      form.setValue('entity_location_id', '');
    }
  }, [watchEntityId, profile, form]);

  // --- Submit handlers ---
  const handleSubmit = async (data: ProfileFormData) => {
    try {
      // Validate: department entities MUST have a location
      if (data.agent_type === AgentType.ENTITY_AGENT && data.entity_id) {
        const entity = entities.find(e => e.id === data.entity_id);
        if (entity?.entity_type === 'department' && !data.entity_location_id) {
          toast({
            variant: 'destructive',
            title: 'Site obligatoire',
            description: 'Les agents de département doivent être assignés à un site spécifique.',
          });
          return;
        }
      }

      // Non-supervisors get defaults for capabilities
      const capabilities = data.is_supervisor
        ? { can_escalate: data.can_escalate, can_assign_tasks: data.can_assign_tasks, can_reassign: data.can_reassign }
        : { can_escalate: true, can_assign_tasks: false, can_reassign: false };

      const updateData: AgentProfileUpdateRequest = {
        agent_type: data.agent_type,
        is_supervisor: data.is_supervisor,
        ministry_id: data.agent_type === AgentType.MINISTRY_AGENT ? data.ministry_id ?? undefined : undefined,
        entity_id: data.agent_type === AgentType.ENTITY_AGENT && data.entity_id ? data.entity_id : undefined,
        entity_location_id:
          data.agent_type === AgentType.ENTITY_AGENT &&
          data.entity_location_id &&
          data.entity_location_id !== 'ALL_SITES'
            ? data.entity_location_id
            : null,
        rbac_role_id: data.rbac_role_id || undefined,
        ...capabilities,
        can_approve_unlimited: data.can_approve_unlimited,
        max_approval_amount: data.can_approve_unlimited ? undefined : data.max_approval_amount ?? undefined,
        working_hours_start: data.working_hours_start,
        working_hours_end: data.working_hours_end,
        working_days: data.working_days,
        is_active: data.is_active,
        is_backup_agent: data.is_backup_agent,
        specializations: data.specializations,
      };

      await updateMutation.mutateAsync({ profileId, data: updateData });

      // Also save info bar changes if it's open (unified save)
      if (editingInfo && profile) {
        const userChanges: { email?: string; phone_number?: string } = {};
        if (infoEmail && infoEmail !== profile.user_email) userChanges.email = infoEmail;
        if (infoPhone !== (profile.user_phone || '')) userChanges.phone_number = infoPhone || undefined;
        if (Object.keys(userChanges).length > 0) {
          const result = await adminUsersApi.updateUser(profile.user_id, userChanges) as Record<string, unknown>;
          if (result?._email_changed && !result?._email_sent) {
            toast({
              variant: 'destructive',
              title: 'Email modifié — activation non envoyée',
              description: "L'email d'activation n'a pas pu être envoyé. Vérifiez la configuration SMTP.",
            });
          }
        }
        setEditingInfo(false);
      }

      queryClient.invalidateQueries({ queryKey: ['agent-profile', profileId] });

      toast({
        title: 'Profil mis à jour',
        description: 'Les modifications ont été enregistrées.',
      });
      setIsEditing(false);
    } catch (error: unknown) {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: (error instanceof Error ? error.message : '') || 'Impossible de mettre à jour le profil',
      });
    }
  };

  const handleDeactivate = async () => {
    try {
      await deactivateMutation.mutateAsync({
        profileId,
        reason: deactivateReason || undefined,
      });
      toast({ title: 'Agent désactivé', description: 'Le profil agent a été désactivé.' });
      setDeactivateReason('');
    } catch (error: unknown) {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: (error instanceof Error ? error.message : '') || "Impossible de désactiver l'agent",
      });
    }
  };

  const handleReactivate = async () => {
    try {
      await reactivateMutation.mutateAsync(profileId);
      toast({ title: 'Agent réactivé', description: 'Le profil agent a été réactivé.' });
    } catch (error: unknown) {
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: (error instanceof Error ? error.message : '') || "Impossible de réactiver l'agent",
      });
    }
  };

  // --- Inline info edit helpers ---
  const startEditingInfo = () => {
    if (!profile) return;
    setInfoEmail(profile.user_email || '');
    setInfoPhone(profile.user_phone || '');
    setInfoEntityId(profile.entity_id || '');
    setInfoLocationId(profile.entity_location_id || '');
    setEditingInfo(true);
  };

  const cancelEditingInfo = () => {
    setEditingInfo(false);
  };

  // Derive entity code for location fetching during inline edit
  const infoSelectedEntity = entities.find(e => e.id === infoEntityId);
  const infoSelectedEntityCode = infoSelectedEntity?.code;

  // Fetch locations for the entity selected in the info bar edit
  const { data: infoEntityLocations, isLoading: isLoadingInfoLocations } = useLocationsByEntity(
    infoSelectedEntityCode || '',
    !!infoSelectedEntityCode && editingInfo
  );

  // Reset location when entity changes in info edit
  useEffect(() => {
    if (editingInfo && profile && infoEntityId !== profile.entity_id) {
      setInfoLocationId('');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [infoEntityId]);

  const emailChanged = editingInfo && profile && infoEmail !== profile.user_email;

  const handleSaveInfo = async () => {
    if (!profile) return;
    setSavingInfo(true);
    try {
      // Sequential execution: profile first, then email (most risky last)
      // This prevents inconsistent state if one operation fails.

      // 1) Agent profile update (entity/location) — only if changed
      const profileChanges: AgentProfileUpdateRequest = {};
      if (infoEntityId && infoEntityId !== (profile.entity_id || '')) {
        profileChanges.entity_id = infoEntityId;
      }
      const newLocId = infoLocationId || null;
      const oldLocId = profile.entity_location_id || null;
      if (newLocId !== oldLocId) {
        profileChanges.entity_location_id = newLocId;
      }
      if (Object.keys(profileChanges).length > 0) {
        await updateMutation.mutateAsync({ profileId, data: profileChanges });
      }

      // 2) User update (email/phone) — only if changed (done AFTER profile to avoid
      //    account deactivation if profile update fails)
      const userChanges: { email?: string; phone_number?: string } = {};
      if (infoEmail && infoEmail !== profile.user_email) userChanges.email = infoEmail;
      if (infoPhone !== (profile.user_phone || '')) userChanges.phone_number = infoPhone || undefined;

      let emailSentOk = true;
      if (Object.keys(userChanges).length > 0) {
        const result = await adminUsersApi.updateUser(profile.user_id, userChanges) as Record<string, unknown>;
        if (result?._email_changed && !result?._email_sent) {
          emailSentOk = false;
        }
      }

      if (Object.keys(profileChanges).length === 0 && Object.keys(userChanges).length === 0) {
        setEditingInfo(false);
        return;
      }

      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['agent-profile', profileId] });

      if (emailChanged && !emailSentOk) {
        toast({
          variant: 'destructive',
          title: 'Email modifié — activation non envoyée',
          description: "L'email a été modifié et le compte désactivé, mais l'email d'activation n'a pas pu être envoyé. Vérifiez la configuration SMTP.",
        });
      } else {
        toast({
          title: 'Información actualizada',
          description: emailChanged
            ? 'Email modificado. La cuenta ha sido desactivada y se ha enviado un nuevo enlace de activación.'
            : 'Los cambios han sido guardados.',
        });
      }
      setEditingInfo(false);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '';
      toast({
        variant: 'destructive',
        title: 'Error',
        description: message || 'No se pudieron guardar los cambios.',
      });
    } finally {
      setSavingInfo(false);
    }
  };

  // --- Loading state ---
  if (profileLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  // --- Error state ---
  if (profileError || !profile) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Agent non trouvé</h1>
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              Le profil agent demandé n&apos;existe pas ou vous n&apos;avez pas les permissions nécessaires.
            </p>
            <Button className="mt-4" onClick={() => router.push('/dashboard/admin/agents')}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const agentTypeLabel = profile.agent_type === AgentType.MINISTRY_AGENT ? 'Agent Ministère' : 'Agent Entité';
  const organizationName = profile.ministry_name || profile.entity_name || '-';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
              <UserCog className="h-6 w-6" />
              {profile.user_full_name || 'Agent'}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={profile.is_active ? 'default' : 'secondary'}>
                {profile.is_active ? 'Actif' : 'Inactif'}
              </Badge>
              <Badge variant="outline">{agentTypeLabel}</Badge>
              {profile.is_supervisor && (
                <Badge variant="outline" className="bg-purple-100 text-purple-800">
                  Superviseur
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Agent Navigation */}
          <div className="flex items-center gap-1 mr-2 border-r pr-4">
            <Button
              variant="outline"
              size="icon"
              onClick={() => prevAgentId && router.push(`/${locale}/dashboard/admin/agents/${prevAgentId}`)}
              disabled={!prevAgentId || neighborsLoading}
              title={prevAgentId ? 'Agent précédent' : "Pas d'agent précédent"}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm text-muted-foreground px-2 min-w-[50px] text-center">
              {neighborsLoading ? (
                <Loader2 className="h-3 w-3 animate-spin inline" />
              ) : neighborsError ? (
                <span className="text-destructive" title="Échec du chargement">!</span>
              ) : neighbors ? (
                `${neighbors.position}/${neighbors.total}`
              ) : (
                '- / -'
              )}
            </span>
            <Button
              variant="outline"
              size="icon"
              onClick={() => nextAgentId && router.push(`/${locale}/dashboard/admin/agents/${nextAgentId}`)}
              disabled={!nextAgentId || neighborsLoading}
              title={nextAgentId ? 'Agent suivant' : "Pas d'agent suivant"}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          {profile.is_active ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" className="text-red-600">
                  <PowerOff className="h-4 w-4 mr-2" />
                  Désactiver
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Désactiver l&apos;agent ?</AlertDialogTitle>
                  <AlertDialogDescription>
                    L&apos;agent ne pourra plus traiter de dossiers. Cette action est réversible.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <div className="py-4">
                  <Input
                    placeholder="Raison de la désactivation (optionnel)"
                    value={deactivateReason}
                    onChange={(e) => setDeactivateReason(e.target.value)}
                  />
                </div>
                <AlertDialogFooter>
                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={handleDeactivate}
                    className="bg-red-600 hover:bg-red-700"
                  >
                    {deactivateMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      'Désactiver'
                    )}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : (
            <Button
              variant="outline"
              className="text-green-600"
              onClick={handleReactivate}
              disabled={reactivateMutation.isPending}
            >
              {reactivateMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Power className="h-4 w-4 mr-2" />
              )}
              Réactiver
            </Button>
          )}
        </div>
      </div>

      {/* User Info — compact inline bar (read / edit) */}
      <div className="rounded-lg border bg-card px-4 py-2.5">
        {!editingInfo ? (
          /* ---- READ MODE ---- */
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
            <span className="text-muted-foreground">
              Email: <span className="font-medium text-foreground">{profile.user_email}</span>
            </span>
            <span className="text-muted-foreground">
              Tél: <span className="font-medium text-foreground">{profile.user_phone || '-'}</span>
            </span>
            <span className="text-muted-foreground">
              Organisation: <span className="font-medium text-foreground">{organizationName}</span>
            </span>
            {profile.agent_type === AgentType.ENTITY_AGENT && (
              <span className="text-muted-foreground">
                Site: <span className="font-medium text-foreground">
                  {profile.location_name || 'Todas las ubicaciones'}
                </span>
              </span>
            )}
            <Button variant="outline" size="sm" className="ml-auto h-8 px-3 text-primary border-primary/30 hover:bg-primary/5" onClick={startEditingInfo}>
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Editar info
            </Button>
          </div>
        ) : (
          /* ---- EDIT MODE ---- */
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Email */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Email</label>
                <Input
                  type="email"
                  value={infoEmail}
                  onChange={(e) => setInfoEmail(e.target.value)}
                  placeholder="email@ejemplo.com"
                  className="h-8 text-sm"
                />
              </div>
              {/* Teléfono */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Teléfono</label>
                <Input
                  value={infoPhone}
                  onChange={(e) => setInfoPhone(e.target.value)}
                  placeholder="+240XXXXXXXXX"
                  className="h-8 text-sm"
                />
              </div>
              {/* Organisation (Entity) */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Organisation</label>
                <Select value={infoEntityId} onValueChange={(v) => setInfoEntityId(v)}>
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue placeholder="Seleccionar entidad" />
                  </SelectTrigger>
                  <SelectContent>
                    {entities.map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {/* Site (Location) */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Site</label>
                <Select
                  value={infoLocationId || 'ALL_SITES'}
                  onValueChange={(v) => setInfoLocationId(v === 'ALL_SITES' ? '' : v)}
                  disabled={!infoEntityId || isLoadingInfoLocations}
                >
                  <SelectTrigger className="h-8 text-sm">
                    <SelectValue placeholder={isLoadingInfoLocations ? 'Cargando...' : 'Todas las ubicaciones'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ALL_SITES">Todas las ubicaciones</SelectItem>
                    {infoEntityLocations?.map((loc) => (
                      <SelectItem key={loc.id} value={loc.id}>
                        {loc.location_name} — {loc.city}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Warning si email modifié */}
            {emailChanged && (
              <Alert variant="destructive" className="py-2">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription className="text-xs">
                  La cuenta será desactivada y se enviará un nuevo enlace de activación al nuevo email.
                </AlertDescription>
              </Alert>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 justify-end">
              <Button variant="ghost" size="sm" className="h-7" onClick={cancelEditingInfo} disabled={savingInfo}>
                Cancelar
              </Button>
              <Button size="sm" className="h-7" onClick={handleSaveInfo} disabled={savingInfo}>
                {savingInfo ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Save className="h-3.5 w-3.5 mr-1" />}
                Guardar
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="profile" className="flex items-center gap-2">
            <Settings className="h-4 w-4" />
            Profil
          </TabsTrigger>
          <TabsTrigger value="activity" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Activité
          </TabsTrigger>
        </TabsList>

        {/* ========== Profile Tab ========== */}
        <TabsContent value="profile" className="space-y-4 mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Configuration du profil</CardTitle>
                <CardDescription>
                  Type, permissions et paramètres de l&apos;agent
                </CardDescription>
              </div>
              {!isEditing ? (
                <Button onClick={() => { setIsEditing(true); if (!editingInfo) startEditingInfo(); }}>Modifier</Button>
              ) : (
                <Button variant="ghost" onClick={() => setIsEditing(false)}>Annuler</Button>
              )}
            </CardHeader>
            <CardContent>
              {!isEditing ? (
                /* ---- Read-only view — structured with separators ---- */
                <div className="space-y-0 divide-y">
                  {/* Section 1: Type + Supervisor + Entity */}
                  <div className="pb-3 space-y-2">
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
                      <span className="text-muted-foreground">
                        Type: <span className="font-medium text-foreground">{agentTypeLabel}</span>
                      </span>
                      <span className="text-muted-foreground">
                        Superviseur: <span className={`font-medium ${profile.is_supervisor ? 'text-green-600' : 'text-foreground'}`}>
                          {profile.is_supervisor ? 'Oui' : 'Non'}
                        </span>
                      </span>
                    </div>
                    <div className="text-sm">
                      <span className="text-muted-foreground">
                        {profile.agent_type === AgentType.MINISTRY_AGENT ? 'Ministère' : 'Entité'}:{' '}
                      </span>
                      <span className="font-medium text-foreground">{organizationName}</span>
                    </div>
                    {profile.agent_type === AgentType.ENTITY_AGENT && (
                      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
                        <span className="text-muted-foreground">
                          Site: <span className="font-medium text-foreground">
                            {profile.location_name
                              ? `${profile.location_name} — ${profile.location_city || ''}`
                              : 'Todas las ubicaciones'}
                          </span>
                        </span>
                        <span className="text-muted-foreground">
                          Créé le: <span className="font-medium text-foreground">
                            {new Date(profile.created_at).toLocaleDateString()}
                          </span>
                        </span>
                      </div>
                    )}
                    {profile.agent_type !== AgentType.ENTITY_AGENT && (
                      <div className="text-sm text-muted-foreground">
                        Créé le: <span className="font-medium text-foreground">
                          {new Date(profile.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Section 2: Capabilities + Approval */}
                  <div className="py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      {profile.is_supervisor && (
                        <>
                          {profile.can_escalate && <Badge variant="outline" className="text-xs">Peut escalader</Badge>}
                          {profile.can_assign_tasks && <Badge variant="outline" className="text-xs">Peut assigner</Badge>}
                          {profile.can_reassign && <Badge variant="outline" className="text-xs">Peut réassigner</Badge>}
                          {profile.is_backup_agent && <Badge variant="outline" className="text-xs">Agent de backup</Badge>}
                        </>
                      )}
                      {profile.can_approve_unlimited && (
                        <Badge variant="outline" className="text-xs bg-green-50 border-green-200">Approbation illimitée</Badge>
                      )}
                      {!profile.can_approve_unlimited && profile.max_approval_amount && (
                        <Badge variant="outline" className="text-xs">
                          Max: {profile.max_approval_amount.toLocaleString()} XAF
                        </Badge>
                      )}
                      {!profile.is_supervisor && !profile.can_approve_unlimited && !profile.max_approval_amount && (
                        <span className="text-xs text-muted-foreground italic">Aucune capacité spéciale</span>
                      )}
                    </div>
                  </div>

                  {/* Section 3: Schedule */}
                  <div className="pt-3">
                    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                      <span className="text-muted-foreground">
                        Horaires: <span className="font-medium text-foreground">
                          {profile.working_hours_start || '08:00'} - {profile.working_hours_end || '17:00'}
                        </span>
                      </span>
                      <div className="flex items-center gap-1.5">
                        <span className="text-muted-foreground">Jours:</span>
                        <div className="flex gap-0.5">
                          {[
                            { value: 1, label: 'L' },
                            { value: 2, label: 'M' },
                            { value: 3, label: 'M' },
                            { value: 4, label: 'J' },
                            { value: 5, label: 'V' },
                            { value: 6, label: 'S' },
                            { value: 0, label: 'D' },
                          ].map((day) => (
                            <Badge
                              key={day.value}
                              variant={(profile.working_days || [1, 2, 3, 4, 5]).includes(day.value) ? 'default' : 'outline'}
                              className="text-[10px] h-5 w-5 p-0 justify-center"
                            >
                              {day.label}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                /* ---- Edit form (using extracted components) ---- */
                <Form {...form}>
                  <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
                    {/* Organization */}
                    <AgentOrganizationFields
                      form={form}
                      ministries={ministries}
                      entities={entities}
                      entityLocations={entityLocations}
                      isLoadingMinistries={isLoadingMinistries}
                      isLoadingEntities={isLoadingEntities}
                      isLoadingLocations={isLoadingLocations}
                      isEditMode
                    />

                    <Separator />

                    {/* Role & Supervisor */}
                    <AgentRoleFields
                      form={form}
                      rbacRoles={rbacRoles}
                      isLoadingRoles={isLoadingRoles}
                    />

                    {/* Capabilities — supervisor only */}
                    {watchIsSupervisor && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-3">Capacités superviseur</h4>
                          <AgentCapabilitiesFields form={form} />
                          {/* Backup agent — edit-only field */}
                          <div className="mt-4">
                            <FormField
                              control={form.control}
                              name="is_backup_agent"
                              render={({ field }) => (
                                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                                  <Checkbox
                                    checked={field.value}
                                    onCheckedChange={field.onChange}
                                  />
                                  <div className="space-y-1 leading-none">
                                    <label className="text-sm font-medium leading-none">Agent de backup</label>
                                    <p className="text-xs text-muted-foreground">
                                      Reçoit les tâches quand les agents principaux sont indisponibles.
                                    </p>
                                  </div>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {/* Approval Limits — payment entities only */}
                    {isPaymentEntity && (
                      <>
                        <Separator />
                        <div>
                          <h4 className="text-sm font-medium mb-3">Limites d&apos;approbation</h4>
                          <AgentApprovalFields form={form} />
                        </div>
                      </>
                    )}

                    <Separator />

                    {/* Schedule */}
                    <div>
                      <h4 className="text-sm font-medium mb-3">Horaires de travail</h4>
                      <AgentScheduleFields form={form} />
                    </div>

                    <div className="flex justify-end gap-3 pt-4">
                      <Button type="button" variant="outline" onClick={() => setIsEditing(false)}>
                        Annuler
                      </Button>
                      <Button type="submit" disabled={updateMutation.isPending}>
                        {updateMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Enregistrer
                      </Button>
                    </div>
                  </form>
                </Form>
              )}
            </CardContent>
          </Card>

          {/* Deactivation Info */}
          {!profile.is_active && profile.deactivated_at && (
            <Card className="border-orange-200 bg-orange-50">
              <CardHeader>
                <CardTitle className="text-orange-800 flex items-center gap-2">
                  <XCircle className="h-5 w-5" />
                  Profil désactivé
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-2 md:grid-cols-2 text-sm">
                  <div>
                    <p className="text-muted-foreground">Désactivé le</p>
                    <p className="font-medium">{new Date(profile.deactivated_at).toLocaleString()}</p>
                  </div>
                  {profile.deactivation_reason && (
                    <div>
                      <p className="text-muted-foreground">Raison</p>
                      <p className="font-medium">{profile.deactivation_reason}</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* ========== Activity Tab (merged Workload + Performance) ========== */}
        <TabsContent value="activity" className="mt-4">
          <AgentActivityTab
            workload={workload}
            performance={performance}
            isLoading={workloadLoading || performanceLoading}
          />
        </TabsContent>

      </Tabs>
    </div>
  );
}
