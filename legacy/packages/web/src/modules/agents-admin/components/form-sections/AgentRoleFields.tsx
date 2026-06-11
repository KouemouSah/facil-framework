'use client';

import { useEffect, useRef } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { SafeSelect } from '@/components/ui/safe-select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

interface RoleOption {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  default_agent_config?: Record<string, unknown> | null;
}

interface AgentRoleFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
  rbacRoles: RoleOption[];
  isLoadingRoles: boolean;
  /** Inline mode: supervisor(30%) + RBAC role(70%) on same row */
  inline?: boolean;
}

export function AgentRoleFields({
  form,
  rbacRoles,
  isLoadingRoles,
  inline = false,
}: AgentRoleFieldsProps) {
  const t = useTranslations('admin.agents');
  const watchIsSupervisor = form.watch('is_supervisor');
  const watchRbacRoleId = form.watch('rbac_role_id');
  const prevRoleIdRef = useRef<string | null>(null);

  // Check supervisor + role compatibility
  const selectedRole = rbacRoles.find(r => r.id === watchRbacRoleId);
  const hasSupervisorMismatch = watchIsSupervisor && selectedRole && !selectedRole.code.includes('supervisor');
  const hasDefaultConfig = !!selectedRole?.default_agent_config;

  // Auto-fill capabilities from role defaults when role changes
  useEffect(() => {
    if (!watchRbacRoleId || watchRbacRoleId === prevRoleIdRef.current) return;
    prevRoleIdRef.current = watchRbacRoleId;

    const config = selectedRole?.default_agent_config;
    if (!config) return;

    // Apply defaults — only set fields that have values in the config
    if (config.is_supervisor !== undefined) form.setValue('is_supervisor', !!config.is_supervisor);
    if (config.can_escalate !== undefined) form.setValue('can_escalate', !!config.can_escalate);
    if (config.can_assign_tasks !== undefined) form.setValue('can_assign_tasks', !!config.can_assign_tasks);
    if (config.can_reassign !== undefined) form.setValue('can_reassign', !!config.can_reassign);
    if (config.can_approve_unlimited !== undefined) form.setValue('can_approve_unlimited', !!config.can_approve_unlimited);
    if (config.max_approval_amount !== undefined) form.setValue('max_approval_amount', config.max_approval_amount);
  }, [watchRbacRoleId, selectedRole, form]);

  const roleItems = rbacRoles.map(r => ({
    value: r.id,
    label: `${r.name} (${r.code})`,
    description: r.description ?? undefined,
  }));

  const supervisorField = (
    <FormField
      control={form.control}
      name="is_supervisor"
      render={({ field }) => (
        <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
          <FormControl>
            <Checkbox
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          </FormControl>
          <div className="space-y-1 leading-none">
            <FormLabel>{t('form.supervisor')}</FormLabel>
            {!inline && (
              <FormDescription>
                {t('form.supervisorDescFull')}
              </FormDescription>
            )}
          </div>
        </FormItem>
      )}
    />
  );

  const rbacRoleField = (
    <FormField
      control={form.control}
      name="rbac_role_id"
      render={({ field }) => (
        <FormItem>
          <FormLabel className="flex items-center gap-2">
            {t('form.rbacRole')} <span className="text-destructive">*</span>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Info className="h-4 w-4 text-muted-foreground cursor-help" />
                </TooltipTrigger>
                <TooltipContent className="max-w-xs">
                  <p>{t('form.rbacTooltip')}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </FormLabel>
          <FormControl>
            <SafeSelect
              value={field.value || ''}
              onValueChange={field.onChange}
              items={roleItems}
              isLoading={isLoadingRoles}
              emptyMessage={t('form.noRoles')}
              placeholder={t('form.selectRole')}
            />
          </FormControl>
          <FormMessage />
        </FormItem>
      )}
    />
  );

  return (
    <div className="space-y-4">
      {/* Supervisor + RBAC Role — inline(30/70) or stacked */}
      {inline ? (
        <div className="grid grid-cols-[30%_1fr] gap-4 items-start">
          {supervisorField}
          {rbacRoleField}
        </div>
      ) : (
        <>
          {supervisorField}
          {rbacRoleField}
        </>
      )}

      {/* Role defaults applied info */}
      {hasDefaultConfig && (
        <Alert variant="default" className="border-blue-300 bg-blue-50">
          <Info className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            {t('form.defaultsApplied')}
          </AlertDescription>
        </Alert>
      )}

      {/* Supervisor + Role mismatch warning */}
      {hasSupervisorMismatch && (
        <Alert variant="default" className="border-orange-300 bg-orange-50">
          <Info className="h-4 w-4 text-orange-600" />
          <AlertDescription className="text-orange-800">
            {t('form.supervisorMismatch', { roleCode: selectedRole?.code })}
          </AlertDescription>
        </Alert>
      )}

    </div>
  );
}
