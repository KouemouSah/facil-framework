'use client';

/**
 * Agent Profile Form Component
 * Form for creating or editing agent profiles
 *
 * @module agents-admin/components
 */

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useTranslations } from 'next-intl';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
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
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Loader2 } from 'lucide-react';
import { AgentType } from '../types';
import type { AgentInviteRequest, AgentProfileUpdateRequest } from '../types';

// =============================================================================
// VALIDATION SCHEMAS
// =============================================================================

/**
 * User info schema for invitation (NO password - agent will set it via email link)
 */
const agentUserInviteSchema = z.object({
  email: z.string().email('Email invalide'),
  first_name: z.string().min(2, 'Minimum 2 caractères').max(100),
  last_name: z.string().min(2, 'Minimum 2 caractères').max(100),
  phone_number: z
    .string()
    .regex(/^(222|555|551|333)\d{6}$/, 'Format: 222/555/551/333 + 6 chiffres')
    .optional()
    .or(z.literal('')),
  preferred_language: z.enum(['es', 'fr', 'en']).default('es'),
});

const agentProfileSchema = z.object({
  agent_type: z.nativeEnum(AgentType),
  is_supervisor: z.boolean().default(false),
  entity_id: z.string().uuid().optional().or(z.literal('')),
  ministry_id: z.coerce.number().int().positive().optional(),
  can_approve_unlimited: z.boolean().default(false),
  max_approval_amount: z.coerce.number().positive().optional(),
  can_escalate: z.boolean().default(true),
  can_assign_tasks: z.boolean().default(false),
  can_reassign: z.boolean().default(false),
  specializations: z.array(z.string()).default([]),
  working_hours_start: z.string().optional(),
  working_hours_end: z.string().optional(),
  working_days: z.array(z.number()).default([1, 2, 3, 4, 5]),
});

/**
 * Schema for agent invitation (Step 1 - no password)
 */
const inviteAgentSchema = z.object({
  user: agentUserInviteSchema,
}).merge(agentProfileSchema);

const updateAgentSchema = agentProfileSchema.partial();

type InviteAgentFormData = z.infer<typeof inviteAgentSchema>;
type UpdateAgentFormData = z.infer<typeof updateAgentSchema>;

// =============================================================================
// COMPONENT PROPS
// =============================================================================

interface AgentProfileFormProps {
  mode: 'create' | 'edit';
  initialData?: Partial<UpdateAgentFormData>;
  /**
   * For create mode: receives AgentInviteRequest (no password - sends invitation email)
   * For edit mode: receives AgentProfileUpdateRequest
   */
  onSubmit: (data: AgentInviteRequest | AgentProfileUpdateRequest) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
  ministries?: Array<{ id: number; name: string }>;
  entities?: Array<{ id: string; name: string }>;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function AgentProfileForm({
  mode,
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
  ministries = [],
  entities = [],
}: AgentProfileFormProps) {
  const t = useTranslations('admin.agents');

  // Note: _showMaxAmount kept for future implementation
  const [_showMaxAmount, setShowMaxAmount] = useState(
    initialData?.can_approve_unlimited === false && !!initialData?.max_approval_amount
  );

  const form = useForm<InviteAgentFormData>({
    resolver: zodResolver(mode === 'create' ? inviteAgentSchema : updateAgentSchema),
    defaultValues: {
      user: {
        email: '',
        first_name: '',
        last_name: '',
        phone_number: '',
        preferred_language: 'es',
      },
      agent_type: initialData?.agent_type || AgentType.MINISTRY_AGENT,
      is_supervisor: initialData?.is_supervisor || false,
      ministry_id: initialData?.ministry_id,
      entity_id: initialData?.entity_id || '',
      can_approve_unlimited: initialData?.can_approve_unlimited || false,
      max_approval_amount: initialData?.max_approval_amount,
      can_escalate: initialData?.can_escalate ?? true,
      can_assign_tasks: initialData?.can_assign_tasks || false,
      can_reassign: initialData?.can_reassign || false,
      specializations: initialData?.specializations || [],
      working_hours_start: initialData?.working_hours_start || '08:00',
      working_hours_end: initialData?.working_hours_end || '17:00',
      working_days: initialData?.working_days || [1, 2, 3, 4, 5],
    },
  });

  const watchAgentType = form.watch('agent_type');
  const watchCanApproveUnlimited = form.watch('can_approve_unlimited');

  const handleSubmit = async (data: InviteAgentFormData) => {
    if (mode === 'create') {
      // Invitation flow: No password in request
      await onSubmit(data as AgentInviteRequest);
    } else {
      // For edit mode, exclude user data
      const { user: _user, ...profileData } = data;
      await onSubmit(profileData as AgentProfileUpdateRequest);
    }
  };

  const weekDays = [
    { value: 1, label: t('days.mon') },
    { value: 2, label: t('days.tue') },
    { value: 3, label: t('days.wed') },
    { value: 4, label: t('days.thu') },
    { value: 5, label: t('days.fri') },
    { value: 6, label: t('days.sat') },
    { value: 0, label: t('days.sun') },
  ];

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        {/* User Information - Only for create mode (Invitation Flow) */}
        {mode === 'create' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">{t('form.userInfo')}</CardTitle>
              <p className="text-sm text-muted-foreground">
                {t('form.userInfoDesc')}
              </p>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="user.email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.email')} *</FormLabel>
                    <FormControl>
                      <Input type="email" placeholder={t('form.emailPlaceholder')} {...field} />
                    </FormControl>
                    <FormDescription>
                      {t('form.emailDesc')}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="user.first_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.firstName')} *</FormLabel>
                    <FormControl>
                      <Input placeholder={t('form.firstNamePlaceholder')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="user.last_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.lastName')} *</FormLabel>
                    <FormControl>
                      <Input placeholder={t('form.lastNamePlaceholder')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="user.phone_number"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.phone')}</FormLabel>
                    <FormControl>
                      <Input placeholder={t('form.phonePlaceholder')} {...field} />
                    </FormControl>
                    <FormDescription>{t('form.phoneFormat')}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="user.preferred_language"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.preferredLanguage')}</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('form.selectLanguage')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="es">Español</SelectItem>
                        <SelectItem value="fr">Français</SelectItem>
                        <SelectItem value="en">English</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>
        )}

        {/* Agent Profile Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t('form.profileConfig')}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Type & Organization */}
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="agent_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.agentType')} *</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={t('form.selectType')} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value={AgentType.MINISTRY_AGENT}>{t('form.agentMinistry')}</SelectItem>
                        <SelectItem value={AgentType.ENTITY_AGENT}>{t('form.agentEntity')}</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {watchAgentType === AgentType.MINISTRY_AGENT ? (
                <FormField
                  control={form.control}
                  name="ministry_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.ministry')} *</FormLabel>
                      <Select
                        onValueChange={(v) => field.onChange(parseInt(v))}
                        defaultValue={field.value?.toString()}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder={t('form.selectMinistry')} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {ministries.map((m) => (
                            <SelectItem key={m.id} value={m.id.toString()}>
                              {m.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : (
                <FormField
                  control={form.control}
                  name="entity_id"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.entity')} *</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder={t('form.selectEntity')} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {entities.map((e) => (
                            <SelectItem key={e.id} value={e.id}>
                              {e.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            {/* Role & Permissions */}
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="is_supervisor"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 pt-8">
                    <FormControl>
                      <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>{t('form.supervisor')}</FormLabel>
                      <FormDescription>
                        {t('form.supervisorDesc')}
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />
            </div>

            <Separator />

            {/* Approval Limits */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">{t('form.approvalLimits')}</h4>

              <FormField
                control={form.control}
                name="can_approve_unlimited"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={(checked) => {
                          field.onChange(checked);
                          setShowMaxAmount(!checked);
                        }}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>{t('form.unlimitedApproval')}</FormLabel>
                    </div>
                  </FormItem>
                )}
              />

              {!watchCanApproveUnlimited && (
                <FormField
                  control={form.control}
                  name="max_approval_amount"
                  render={({ field }) => (
                    <FormItem className="max-w-xs">
                      <FormLabel>{t('form.maxAmount')}</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          placeholder={t('form.maxAmountPlaceholder')}
                          {...field}
                          onChange={(e) => field.onChange(e.target.valueAsNumber)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              )}
            </div>

            <Separator />

            {/* Capabilities */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">{t('form.capabilities')}</h4>
              <div className="grid gap-4 md:grid-cols-3">
                <FormField
                  control={form.control}
                  name="can_escalate"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                      <FormControl>
                        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                      <FormLabel className="font-normal">{t('form.canEscalate')}</FormLabel>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="can_assign_tasks"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                      <FormControl>
                        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                      <FormLabel className="font-normal">{t('form.canAssignTasks')}</FormLabel>
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="can_reassign"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-start space-x-3 space-y-0">
                      <FormControl>
                        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                      <FormLabel className="font-normal">{t('form.canReassign')}</FormLabel>
                    </FormItem>
                  )}
                />
              </div>
            </div>

            <Separator />

            {/* Working Hours */}
            <div className="space-y-4">
              <h4 className="text-sm font-medium">{t('form.workingHours')}</h4>
              <div className="grid gap-4 md:grid-cols-2">
                <FormField
                  control={form.control}
                  name="working_hours_start"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.startHour')}</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="working_hours_end"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>{t('form.endHour')}</FormLabel>
                      <FormControl>
                        <Input type="time" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="working_days"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.workingDays')}</FormLabel>
                    <div className="flex flex-wrap gap-2">
                      {weekDays.map((day) => (
                        <Button
                          key={day.value}
                          type="button"
                          variant={field.value?.includes(day.value) ? 'default' : 'outline'}
                          size="sm"
                          onClick={() => {
                            const current = field.value || [];
                            const updated = current.includes(day.value)
                              ? current.filter((d) => d !== day.value)
                              : [...current, day.value];
                            field.onChange(updated);
                          }}
                        >
                          {day.label}
                        </Button>
                      ))}
                    </div>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            {t('form.cancel')}
          </Button>
          <Button type="submit" disabled={isLoading}>
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {mode === 'create' ? t('form.sendInvitation') : t('form.save')}
          </Button>
        </div>
      </form>
    </Form>
  );
}

export default AgentProfileForm;
