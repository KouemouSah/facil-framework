'use client';

import { UseFormReturn } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { Checkbox } from '@/components/ui/checkbox';
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';

interface AgentCapabilitiesFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
}

/**
 * Supervisor capabilities: can_escalate, can_assign_tasks, can_reassign.
 * Only rendered when `is_supervisor = true` (handled by parent).
 */
export function AgentCapabilitiesFields({ form }: AgentCapabilitiesFieldsProps) {
  const t = useTranslations('admin.agents');

  const capabilities = [
    {
      name: 'can_escalate' as const,
      label: t('form.canEscalate'),
      description: t('form.canEscalateDesc'),
    },
    {
      name: 'can_assign_tasks' as const,
      label: t('form.canAssignTasks'),
      description: t('form.canAssignTasksDesc'),
    },
    {
      name: 'can_reassign' as const,
      label: t('form.canReassign'),
      description: t('form.canReassignDesc'),
    },
  ] as const;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {capabilities.map((cap) => (
          <FormField
            key={cap.name}
            control={form.control}
            name={cap.name}
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <div className="space-y-1 leading-none">
                  <FormLabel className="font-normal">{cap.label}</FormLabel>
                  <FormDescription className="text-xs">
                    {cap.description}
                  </FormDescription>
                </div>
              </FormItem>
            )}
          />
        ))}
      </div>
    </div>
  );
}
