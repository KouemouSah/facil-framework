'use client';

import { UseFormReturn } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';

interface AgentApprovalFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
}

/**
 * Approval limits: can_approve_unlimited + max_approval_amount.
 * Only rendered for payment-processing entities (no workflow_codes).
 * Parent controls visibility.
 */
export function AgentApprovalFields({ form }: AgentApprovalFieldsProps) {
  const t = useTranslations('admin.agents');
  const watchCanApproveUnlimited = form.watch('can_approve_unlimited');

  return (
    <div className="space-y-4">
      <FormField
        control={form.control}
        name="can_approve_unlimited"
        render={({ field }) => (
          <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
            <FormControl>
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            </FormControl>
            <div className="space-y-1 leading-none">
              <FormLabel>{t('form.unlimitedApproval')}</FormLabel>
              <FormDescription>
                {t('form.unlimitedApprovalDesc')}
              </FormDescription>
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
                  value={field.value ?? ''}
                />
              </FormControl>
              <FormDescription>
                {t('form.maxAmountDesc')}
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
      )}
    </div>
  );
}
