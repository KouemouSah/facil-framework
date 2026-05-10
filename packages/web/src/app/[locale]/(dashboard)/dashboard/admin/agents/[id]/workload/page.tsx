'use client';

/**
 * Agent Workload Detail Page
 * Detailed view of agent workload and configuration
 *
 * @module dashboard/admin/agents/[id]/workload
 * @date 2025-01-14
 */

import { useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowLeft,
  Loader2,
  Briefcase,
  Clock,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Calendar,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  useAgentProfile,
  useAgentWorkload,
  useUpdateAgentWorkload,
} from '@/modules/agents-admin/hooks';
import { WorkloadStats } from '@/modules/agents-admin/components';
import { AgentAvailability } from '@/modules/agents-admin/types';
import type { AgentWorkloadUpdateRequest } from '@/modules/agents-admin/types';

// =============================================================================
// VALIDATION SCHEMA
// =============================================================================

const workloadSchema = z.object({
  max_concurrent_assignments: z.coerce.number().int().min(1).max(100),
  availability: z.nativeEnum(AgentAvailability),
  availability_reason: z.string().optional(),
  unavailable_until: z.string().optional(),
  active_specializations: z.string().optional(), // comma-separated
  preferred_declaration_types: z.string().optional(), // comma-separated
});

type WorkloadFormData = z.infer<typeof workloadSchema>;

// =============================================================================
// COMPONENT
// =============================================================================

export default function AgentWorkloadPage() {
  const router = useRouter();
  const params = useParams();
  const { toast } = useToast();
  const [isEditing, setIsEditing] = useState(false);

  const profileId = params.id as string;

  // Queries
  const { data: profile, isLoading: profileLoading } = useAgentProfile(profileId);
  const { data: workload, isLoading: workloadLoading } = useAgentWorkload(profileId, !!profile);

  // Mutation
  const updateMutation = useUpdateAgentWorkload();

  // Form
  const form = useForm<WorkloadFormData>({
    resolver: zodResolver(workloadSchema),
    defaultValues: {
      max_concurrent_assignments: workload?.max_concurrent_assignments || 10,
      availability: (workload?.availability as AgentAvailability) || AgentAvailability.AVAILABLE,
      availability_reason: workload?.availability_reason || '',
      unavailable_until: workload?.unavailable_until || '',
      active_specializations: workload?.active_specializations?.join(', ') || '',
      preferred_declaration_types: workload?.preferred_declaration_types?.join(', ') || '',
    },
  });

  const watchAvailability = form.watch('availability');

  // Handlers
  const handleSubmit = async (data: WorkloadFormData) => {
    try {
      const updateData: AgentWorkloadUpdateRequest = {
        max_concurrent_assignments: data.max_concurrent_assignments,
        availability: data.availability,
        availability_reason:
          data.availability !== AgentAvailability.AVAILABLE ? data.availability_reason : undefined,
        unavailable_until:
          data.availability !== AgentAvailability.AVAILABLE ? data.unavailable_until : undefined,
        active_specializations: data.active_specializations
          ? data.active_specializations.split(',').map((s) => s.trim()).filter(Boolean)
          : undefined,
        preferred_declaration_types: data.preferred_declaration_types
          ? data.preferred_declaration_types.split(',').map((s) => s.trim()).filter(Boolean)
          : undefined,
      };

      await updateMutation.mutateAsync({
        profileId,
        data: updateData,
      });

      toast({
        title: 'Configuration mise à jour',
        description: 'Les paramètres de charge de travail ont été enregistrés.',
      });

      setIsEditing(false);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Impossible de mettre à jour la configuration';
      toast({
        variant: 'destructive',
        title: 'Erreur',
        description: message,
      });
    }
  };

  // Loading state
  if (profileLoading || workloadLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[300px] w-full" />
      </div>
    );
  }

  // Error state
  if (!profile) {
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
              Le profil agent demandé n&apos;existe pas.
            </p>
            <Button className="mt-4" onClick={() => router.push('/dashboard/admin/agents')}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const getAvailabilityBadge = (availability: string) => {
    const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
      available: { variant: 'default', label: 'Disponible' },
      on_leave: { variant: 'secondary', label: 'En congé' },
      sick_leave: { variant: 'destructive', label: 'Arrêt maladie' },
      training: { variant: 'outline', label: 'En formation' },
      mission: { variant: 'outline', label: 'En mission' },
      temporarily_unavailable: { variant: 'secondary', label: 'Temporairement indisponible' },
    };
    const config = variants[availability] || { variant: 'outline', label: availability };
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getWorkloadStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      available: 'text-green-600',
      normal: 'text-blue-600',
      busy: 'text-yellow-600',
      overloaded: 'text-red-600',
      unavailable: 'text-gray-600',
    };
    return colors[status] || 'text-gray-600';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              <Briefcase className="h-8 w-8" />
              Charge de Travail
            </h1>
            <p className="text-muted-foreground mt-1">
              {profile.user_full_name} - {profile.ministry_name || profile.entity_name}
            </p>
          </div>
        </div>
      </div>

      {/* Current Status Overview */}
      {workload && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Disponibilité</CardTitle>
            </CardHeader>
            <CardContent>
              {getAvailabilityBadge(workload.availability)}
              {workload.availability_reason && (
                <p className="text-xs text-muted-foreground mt-2">{workload.availability_reason}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Statut Charge</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-lg font-semibold capitalize ${getWorkloadStatusColor(workload.workload_status)}`}>
                {workload.workload_status}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Capacité</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <p className="text-2xl font-bold">{workload.capacity_percentage}%</p>
                <Progress value={workload.capacity_percentage} className="h-2" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Assignations</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {workload.current_assignments}/{workload.max_concurrent_assignments}
              </p>
              <p className="text-xs text-muted-foreground">actives / maximum</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Detailed Stats */}
      {workload && <WorkloadStats workload={workload} />}

      {/* Configuration Card */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Configuration de la charge</CardTitle>
            <CardDescription>
              Paramètres de disponibilité et préférences de l&apos;agent
            </CardDescription>
          </div>
          {!isEditing ? (
            <Button onClick={() => setIsEditing(true)}>
              Modifier
            </Button>
          ) : (
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              Annuler
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {!isEditing ? (
            // Read-only view
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Assignations max simultanées</p>
                  <p className="font-medium">{workload?.max_concurrent_assignments || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Disponibilité</p>
                  <p className="font-medium capitalize">{workload?.availability || 'Non définie'}</p>
                </div>
              </div>

              {workload?.unavailable_until && (
                <div>
                  <p className="text-sm text-muted-foreground">Indisponible jusqu&apos;au</p>
                  <p className="font-medium">{new Date(workload.unavailable_until).toLocaleDateString()}</p>
                </div>
              )}

              <div>
                <p className="text-sm text-muted-foreground">Spécialisations actives</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {workload?.active_specializations?.length ? (
                    workload.active_specializations.map((spec) => (
                      <Badge key={spec} variant="outline" className="text-xs">
                        {spec}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground">Aucune</span>
                  )}
                </div>
              </div>

              <div>
                <p className="text-sm text-muted-foreground">Types de déclarations préférés</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {workload?.preferred_declaration_types?.length ? (
                    workload.preferred_declaration_types.map((type) => (
                      <Badge key={type} variant="outline" className="text-xs">
                        {type}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground">Aucun</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            // Edit form
            <Form {...form}>
              <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="max_concurrent_assignments"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Assignations max simultanées</FormLabel>
                        <FormControl>
                          <Input type="number" min={1} max={100} {...field} />
                        </FormControl>
                        <FormDescription>
                          Nombre maximum de dossiers que l&apos;agent peut traiter en parallèle
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="availability"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Disponibilité</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value={AgentAvailability.AVAILABLE}>Disponible</SelectItem>
                            <SelectItem value={AgentAvailability.ON_LEAVE}>En congé</SelectItem>
                            <SelectItem value={AgentAvailability.SICK_LEAVE}>Arrêt maladie</SelectItem>
                            <SelectItem value={AgentAvailability.TRAINING}>En formation</SelectItem>
                            <SelectItem value={AgentAvailability.MISSION}>En mission</SelectItem>
                            <SelectItem value={AgentAvailability.TEMPORARILY_UNAVAILABLE}>
                              Temporairement indisponible
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {watchAvailability !== AgentAvailability.AVAILABLE && (
                  <div className="grid gap-4 md:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="availability_reason"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Raison</FormLabel>
                          <FormControl>
                            <Input placeholder="Raison de l'indisponibilité" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="unavailable_until"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Jusqu&apos;au</FormLabel>
                          <FormControl>
                            <Input type="date" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="active_specializations"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Spécialisations actives</FormLabel>
                      <FormControl>
                        <Input placeholder="IVA, IRPF, Petroleum (séparés par virgule)" {...field} />
                      </FormControl>
                      <FormDescription>
                        Types de dossiers pour lesquels l&apos;agent est spécialisé
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="preferred_declaration_types"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Types de déclarations préférés</FormLabel>
                      <FormControl>
                        <Input placeholder="iva_destajo, iva_real, irpf (séparés par virgule)" {...field} />
                      </FormControl>
                      <FormDescription>
                        Types de déclarations que l&apos;agent préfère traiter
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

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

      {/* Activity Timeline */}
      {workload && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Historique d&apos;activité
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <div className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Dernière assignation</p>
                  <p className="font-medium">
                    {workload.last_assignment_at
                      ? new Date(workload.last_assignment_at).toLocaleString()
                      : '-'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Dernière complétion</p>
                  <p className="font-medium">
                    {workload.last_completion_at
                      ? new Date(workload.last_completion_at).toLocaleString()
                      : '-'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-orange-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Plus ancien dossier en attente</p>
                  <p className="font-medium">
                    {workload.oldest_pending_assignment_date
                      ? new Date(workload.oldest_pending_assignment_date).toLocaleDateString()
                      : '-'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <TrendingUp className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm text-muted-foreground">Mise à jour</p>
                  <p className="font-medium">
                    {workload.last_updated_at
                      ? new Date(workload.last_updated_at).toLocaleString()
                      : '-'}
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
