'use client';

import { UseFormReturn } from 'react-hook-form';
import { useTranslations } from 'next-intl';
import { Input } from '@/components/ui/input';
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { SafeSelect } from '@/components/ui/safe-select';

const LANGUAGE_OPTIONS = [
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'en', label: 'English' },
];

interface AgentAccountFieldsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  form: UseFormReturn<any>;
}

export function AgentAccountFields({ form }: AgentAccountFieldsProps) {
  const t = useTranslations('admin.agents');

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Email */}
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem className="md:col-span-2">
              <FormLabel>{t('form.email')} <span className="text-destructive">*</span></FormLabel>
              <FormControl>
                <Input type="email" placeholder="agent@facil.gq" {...field} />
              </FormControl>
              <FormDescription>
                {t('form.emailDesc')}
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* First Name */}
        <FormField
          control={form.control}
          name="first_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.firstName')} <span className="text-destructive">*</span></FormLabel>
              <FormControl>
                <Input placeholder={t('form.firstNamePlaceholder')} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Last Name */}
        <FormField
          control={form.control}
          name="last_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.lastName')} <span className="text-destructive">*</span></FormLabel>
              <FormControl>
                <Input placeholder={t('form.lastNamePlaceholder')} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Phone */}
        <FormField
          control={form.control}
          name="phone_number"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.phone')}</FormLabel>
              <FormControl>
                <Input placeholder="222XXXXXX" {...field} />
              </FormControl>
              <FormDescription>{t('form.phoneFormat')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Language */}
        <FormField
          control={form.control}
          name="preferred_language"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('form.preferredLanguage')}</FormLabel>
              <FormControl>
                <SafeSelect
                  value={field.value || 'es'}
                  onValueChange={field.onChange}
                  items={LANGUAGE_OPTIONS}
                  placeholder={t('form.selectLanguage')}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </div>
    </div>
  );
}
