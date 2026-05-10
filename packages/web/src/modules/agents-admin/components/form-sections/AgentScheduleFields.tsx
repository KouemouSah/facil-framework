'use client';

import { UseFormReturn } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';

interface AgentScheduleFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
}

export function AgentScheduleFields({ form }: AgentScheduleFieldsProps) {
  const t = useTranslations('admin.agents');

  const dayOptions = [
    { value: 1, label: t('days.mon') },
    { value: 2, label: t('days.tue') },
    { value: 3, label: t('days.wed') },
    { value: 4, label: t('days.thu') },
    { value: 5, label: t('days.fri') },
    { value: 6, label: t('days.sat') },
    { value: 0, label: t('days.sun') },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Working hours start */}
        <FormField
          control={form.control}
          name="working_hours_start"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.startHour')}</FormLabel>
              <FormControl>
                <Input type="time" {...field} value={field.value || '08:00'} />
              </FormControl>
            </FormItem>
          )}
        />

        {/* Working hours end */}
        <FormField
          control={form.control}
          name="working_hours_end"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.endHour')}</FormLabel>
              <FormControl>
                <Input type="time" {...field} value={field.value || '17:00'} />
              </FormControl>
            </FormItem>
          )}
        />
      </div>

      {/* Working days toggle */}
      <FormField
        control={form.control}
        name="working_days"
        render={({ field }) => (
          <FormItem>
            <FormLabel>{t('form.workingDays')}</FormLabel>
            <div className="flex flex-wrap gap-2">
              {dayOptions.map((day) => (
                <Button
                  key={day.value}
                  type="button"
                  variant={field.value?.includes(day.value) ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    const current: number[] = field.value || [];
                    const updated = current.includes(day.value)
                      ? current.filter((d: number) => d !== day.value)
                      : [...current, day.value];
                    field.onChange(updated);
                  }}
                >
                  {day.label}
                </Button>
              ))}
            </div>
          </FormItem>
        )}
      />
    </div>
  );
}
