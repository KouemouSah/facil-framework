'use client';

import { UseFormReturn } from 'react-hook-form';
import { useEffect, useMemo, useRef } from 'react';
import { useTranslations } from 'next-intl';
import { Checkbox } from '@/components/ui/checkbox';
import { Loader2 } from 'lucide-react';
import {
  FormField,
  FormItem,
  FormLabel,
  FormDescription,
} from '@/components/ui/form';
import type { WorkflowOption } from '@/modules/agents-admin/types';

interface EntityWithWorkflows {
  id: string;
  code: string;
  name: string;
  workflow_codes?: string[];
}

interface AgentSpecializationsFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
  entity: EntityWithWorkflows;
  workflows: WorkflowOption[];
  isLoadingWorkflows: boolean;
}

/**
 * Subtractive specializations: pre-checked from entity.workflow_codes.
 * Admin deselects workflows the agent should NOT handle.
 * Only shown when entity has >1 workflow (parent controls visibility).
 */
export function AgentSpecializationsFields({
  form,
  entity,
  workflows,
  isLoadingWorkflows,
}: AgentSpecializationsFieldsProps) {
  const t = useTranslations('admin.agents');
  const initializedRef = useRef(false);
  const entityWorkflows = useMemo(() => entity.workflow_codes || [], [entity.workflow_codes]);

  // Subtractive: auto-select all entity workflows on first render
  useEffect(() => {
    if (!initializedRef.current && entityWorkflows.length > 0) {
      const currentSpecs: string[] = form.getValues('specializations') || [];
      // Only auto-fill if empty (don't override existing selections in edit mode)
      if (currentSpecs.length === 0) {
        form.setValue('specializations', [...entityWorkflows]);
      }
      initializedRef.current = true;
    }
  }, [entityWorkflows, form]);

  // Filter workflows to only those belonging to this entity
  const entityWorkflowItems = workflows.filter(wf =>
    entityWorkflows.includes(wf.code)
  );

  if (isLoadingWorkflows) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('form.loadingWorkflows')}
      </div>
    );
  }

  if (entityWorkflowItems.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-2">
        {t('form.noWorkflows')}
      </p>
    );
  }

  return (
    <FormField
      control={form.control}
      name="specializations"
      render={({ field }) => (
        <FormItem>
          <FormLabel>{t('form.specializations')}</FormLabel>
          <FormDescription>
            {t('form.specializationsDesc')}
          </FormDescription>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3 mt-2">
            {entityWorkflowItems.map((wf) => {
              const isChecked = field.value?.includes(wf.code) ?? false;
              return (
                <div
                  key={wf.code}
                  className={`flex items-start space-x-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                    isChecked
                      ? 'border-primary bg-primary/5'
                      : 'border-muted hover:border-primary/50'
                  }`}
                  onClick={() => {
                    const current: string[] = field.value || [];
                    const updated = isChecked
                      ? current.filter((c: string) => c !== wf.code)
                      : [...current, wf.code];
                    field.onChange(updated);
                  }}
                >
                  <Checkbox
                    checked={isChecked}
                    onCheckedChange={(checked) => {
                      const current: string[] = field.value || [];
                      const updated = checked
                        ? [...current, wf.code]
                        : current.filter((c: string) => c !== wf.code);
                      field.onChange(updated);
                    }}
                  />
                  <div className="space-y-1">
                    <p className="font-medium text-sm">{wf.name_es}</p>
                    {wf.description_es && (
                      <p className="text-xs text-muted-foreground">
                        {wf.description_es}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </FormItem>
      )}
    />
  );
}
