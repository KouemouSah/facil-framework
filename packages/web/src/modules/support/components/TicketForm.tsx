'use client'

import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Loader2 } from 'lucide-react'
import type { SupportCategory, SupportTicketCreate, TicketPriority } from '../types'
import { getCategoryName } from '../types'

const ticketFormSchema = z.object({
  categoryId: z.string().optional(),
  subject: z.string().min(5, 'Subject must be at least 5 characters'),
  description: z.string().min(20, 'Description must be at least 20 characters'),
  priority: z.string().default('normal'),
})

type TicketFormValues = z.infer<typeof ticketFormSchema>

interface TicketFormProps {
  categories: SupportCategory[]
  isLoading: boolean
  onSubmit: (data: SupportTicketCreate) => Promise<void>
  onCancel?: () => void
  locale: string
}

export function TicketForm({
  categories,
  isLoading,
  onSubmit,
  onCancel,
  locale,
}: TicketFormProps) {
  const t = useTranslations('support')
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<TicketFormValues>({
    resolver: zodResolver(ticketFormSchema),
    defaultValues: {
      categoryId: '',
      subject: '',
      description: '',
      priority: 'normal',
    },
  })

  const handleSubmit = async (values: TicketFormValues) => {
    setSubmitting(true)
    try {
      await onSubmit({
        categoryId: values.categoryId ? parseInt(values.categoryId) : undefined,
        subject: values.subject,
        description: values.description,
        priority: values.priority as TicketPriority,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const activeCategories = categories.filter((c) => c.isActive)

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="categoryId"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('category')}</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectCategory')} />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {activeCategories.map((category) => (
                    <SelectItem key={category.id} value={String(category.id)}>
                      {getCategoryName(category, locale)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormDescription>{t('categoryDescription')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="subject"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('subject')}</FormLabel>
              <FormControl>
                <Input placeholder={t('subjectPlaceholder')} {...field} />
              </FormControl>
              <FormDescription>{t('subjectDescription')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('description')}</FormLabel>
              <FormControl>
                <Textarea
                  placeholder={t('descriptionPlaceholder')}
                  className="min-h-[150px]"
                  {...field}
                />
              </FormControl>
              <FormDescription>{t('descriptionDescription')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="priority"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('priority')}</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder={t('selectPriority')} />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="low">{t('priorities.low')}</SelectItem>
                  <SelectItem value="normal">{t('priorities.normal')}</SelectItem>
                  <SelectItem value="high">{t('priorities.high')}</SelectItem>
                  <SelectItem value="urgent">{t('priorities.urgent')}</SelectItem>
                </SelectContent>
              </Select>
              <FormDescription>{t('priorityDescription')}</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-4">
          {onCancel && (
            <Button type="button" variant="outline" onClick={onCancel}>
              {t('cancel')}
            </Button>
          )}
          <Button type="submit" disabled={submitting || isLoading}>
            {submitting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('submitting')}
              </>
            ) : (
              t('submitTicket')
            )}
          </Button>
        </div>
      </form>
    </Form>
  )
}

export default TicketForm
