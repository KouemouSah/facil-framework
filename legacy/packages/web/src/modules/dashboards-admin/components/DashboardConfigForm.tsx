/**
 * DashboardConfigForm — inline form for one dashboard's iframe config.
 *
 * Supports BOTH providers (Looker Studio + Grafana) via a radio toggle.
 *
 * Zod regex matches the BD CHECK constraints (mig 317 + 319) and the
 * Pydantic regex (DashboardConfigUpdateRequest). Three layers of defense:
 * Zod (instant feedback) -> Pydantic (422) -> BD CHECK (last-resort).
 */

'use client'

import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useTranslations, useFormatter } from 'next-intl'
import {
  Database, AlertCircle, CheckCircle2, Loader2, BarChart3, Activity,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import {
  Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage,
} from '@/components/ui/form'
import { useToast } from '@/hooks/use-toast'

import { useUpdateDashboardConfig } from '../hooks/useUpdateDashboardConfig'
import type {
  DashboardConfigDTO, DashboardConfigSource, DashboardProvider,
} from '../types'

// Patterns must mirror exactly:
//   - Pydantic: DashboardConfigUpdateRequest (regex + length)
//   - BD CHECK: chk_looker_*_format / chk_grafana_*_format (mig 317 + 319)
const REPORT_ID_PATTERN = /^[a-zA-Z0-9_-]{8,64}$/
const PAGE_ID_PATTERN = /^[a-zA-Z0-9_]{1,32}$/
const GRAFANA_UID_PATTERN = /^[a-zA-Z0-9_-]{4,40}$/

const SOURCE_BADGE: Record<DashboardConfigSource, 'default' | 'secondary' | 'outline'> = {
  db: 'default',
  env_fallback: 'secondary',
  unset: 'outline',
}

interface Props {
  config: DashboardConfigDTO
}

export function DashboardConfigForm({ config }: Props) {
  const t = useTranslations('admin.dashboards.config')
  const format = useFormatter()
  const { toast } = useToast()
  const mutation = useUpdateDashboardConfig()

  // The schema validates the active provider's required field. The other
  // provider's fields can stay empty without erroring — admin can switch
  // back later without re-typing.
  const schema = z
    .object({
      provider: z.enum(['looker_studio', 'grafana']),
      looker_report_id: z.string().or(z.literal('')).optional().nullable(),
      looker_page_id: z.string().or(z.literal('')).optional().nullable(),
      grafana_dashboard_uid: z.string().or(z.literal('')).optional().nullable(),
      grafana_org_id: z.coerce.number().int().min(1).max(999),
      is_active: z.boolean(),
    })
    .superRefine((data, ctx) => {
      if (data.provider === 'looker_studio') {
        const v = data.looker_report_id ?? ''
        if (!REPORT_ID_PATTERN.test(v)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ['looker_report_id'],
            message: t('form.reportIdInvalid'),
          })
        }
        const p = data.looker_page_id ?? ''
        if (p && !PAGE_ID_PATTERN.test(p)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ['looker_page_id'],
            message: t('form.pageIdInvalid'),
          })
        }
      } else if (data.provider === 'grafana') {
        const u = data.grafana_dashboard_uid ?? ''
        if (!GRAFANA_UID_PATTERN.test(u)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            path: ['grafana_dashboard_uid'],
            message: t('form.grafanaUidInvalid', {
              defaultValue:
                'Format invalide (4-40 caractères alphanumériques, tirets et soulignés).',
            }),
          })
        }
      }
    })

  type FormValues = z.infer<typeof schema>

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      provider: config.provider,
      looker_report_id: config.looker_report_id ?? '',
      looker_page_id: config.looker_page_id ?? '',
      grafana_dashboard_uid: config.grafana_dashboard_uid ?? '',
      grafana_org_id: config.grafana_org_id || 1,
      is_active: config.is_active,
    },
  })

  // Watch provider so the conditional UI re-renders on toggle.
  const watchedProvider = form.watch('provider') as DashboardProvider

  const onSubmit = (values: FormValues) => {
    const body = {
      provider: values.provider,
      // Send null when empty so the BD column ends up NULL, not "".
      looker_report_id: values.looker_report_id || null,
      looker_page_id: values.looker_page_id || null,
      grafana_dashboard_uid: values.grafana_dashboard_uid || null,
      grafana_org_id: values.grafana_org_id,
      is_active: values.is_active,
    }
    mutation.mutate(
      { dashboardId: config.dashboard_id, body },
      {
        onSuccess: () => {
          toast({
            title: t('form.saveSuccess'),
            description: config.label,
          })
        },
        onError: (err: unknown) => {
          const status = (err as { response?: { status?: number } })?.response?.status
          const detail =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            t('form.saveError')
          toast({
            variant: 'destructive',
            title: status === 429 ? t('form.rateLimitError') : t('form.saveError'),
            description: detail,
          })
        },
      },
    )
  }

  return (
    <div className="rounded-lg border bg-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold text-lg">{config.label}</h3>
            <Badge variant={SOURCE_BADGE[config.source]} className="font-mono text-xs">
              {t(`source.${config.source}`)}
            </Badge>
            <Badge variant="outline" className="font-mono text-xs flex items-center gap-1">
              {config.provider === 'grafana' ? (
                <Activity className="h-3 w-3" />
              ) : (
                <BarChart3 className="h-3 w-3" />
              )}
              {config.provider === 'grafana' ? 'Grafana' : 'Looker Studio'}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">{config.description}</p>
        </div>
        <div className="text-xs text-muted-foreground text-right">
          {config.source === 'db' && config.updated_at ? (
            <>
              <div>
                {t('updatedAt', {
                  date: format.dateTime(new Date(config.updated_at), {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  }),
                })}
              </div>
              {config.updated_by && (
                <div className="font-mono text-[10px] mt-0.5">
                  {config.updated_by.slice(0, 8)}…
                </div>
              )}
            </>
          ) : (
            <div className="italic">{t('neverUpdated')}</div>
          )}
        </div>
      </div>

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          {/* Provider toggle */}
          <FormField
            control={form.control}
            name="provider"
            render={({ field }) => (
              <FormItem className="space-y-2">
                <FormLabel>
                  {t('form.providerLabel', { defaultValue: 'Provider' })}
                </FormLabel>
                <FormControl>
                  <RadioGroup
                    value={field.value}
                    onValueChange={field.onChange}
                    className="flex gap-4"
                  >
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="looker_studio" id={`looker-${config.dashboard_id}`} />
                      <Label
                        htmlFor={`looker-${config.dashboard_id}`}
                        className="flex items-center gap-1 cursor-pointer"
                      >
                        <BarChart3 className="h-4 w-4" />
                        Looker Studio
                      </Label>
                    </div>
                    <div className="flex items-center space-x-2">
                      <RadioGroupItem value="grafana" id={`grafana-${config.dashboard_id}`} />
                      <Label
                        htmlFor={`grafana-${config.dashboard_id}`}
                        className="flex items-center gap-1 cursor-pointer"
                      >
                        <Activity className="h-4 w-4" />
                        Grafana
                      </Label>
                    </div>
                  </RadioGroup>
                </FormControl>
                <FormDescription className="text-xs">
                  {t('form.providerHelp', {
                    defaultValue:
                      'Switcher entre les deux providers — chacun garde sa config indépendante.',
                  })}
                </FormDescription>
              </FormItem>
            )}
          />

          {/* Looker Studio fields — visible when provider=looker_studio */}
          {watchedProvider === 'looker_studio' && (
            <>
              <FormField
                control={form.control}
                name="looker_report_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.reportIdLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        value={field.value ?? ''}
                        placeholder={t('form.reportIdPlaceholder')}
                        className="font-mono text-sm"
                        autoComplete="off"
                        spellCheck={false}
                      />
                    </FormControl>
                    <FormDescription>{t('form.reportIdHelp')}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="looker_page_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('form.pageIdLabel')}</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        value={field.value ?? ''}
                        placeholder={t('form.pageIdPlaceholder')}
                        className="font-mono text-sm"
                        autoComplete="off"
                        spellCheck={false}
                      />
                    </FormControl>
                    <FormDescription>{t('form.pageIdHelp')}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          )}

          {/* Grafana fields — visible when provider=grafana */}
          {watchedProvider === 'grafana' && (
            <>
              <FormField
                control={form.control}
                name="grafana_dashboard_uid"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t('form.grafanaUidLabel', { defaultValue: 'Grafana Dashboard UID' })}
                    </FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        value={field.value ?? ''}
                        placeholder={t('form.grafanaUidPlaceholder', {
                          defaultValue: 'ex: facil-treasury',
                        })}
                        className="font-mono text-sm"
                        autoComplete="off"
                        spellCheck={false}
                      />
                    </FormControl>
                    <FormDescription>
                      {t('form.grafanaUidHelp', {
                        defaultValue:
                          'UID stable du dashboard Grafana (ex: facil-treasury, facil-agents).',
                      })}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="grafana_org_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      {t('form.grafanaOrgIdLabel', { defaultValue: 'Grafana Organization ID' })}
                    </FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={1}
                        max={999}
                        {...field}
                        className="font-mono text-sm w-32"
                      />
                    </FormControl>
                    <FormDescription>
                      {t('form.grafanaOrgIdHelp', {
                        defaultValue: 'Default 1 (single-org Grafana Cloud).',
                      })}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          )}

          <FormField
            control={form.control}
            name="is_active"
            render={({ field }) => (
              <FormItem className="flex items-center justify-between rounded-md border p-3">
                <div className="space-y-0.5">
                  <FormLabel>{t('form.isActiveLabel')}</FormLabel>
                  <FormDescription className="text-xs">
                    {t('form.isActiveHelp')}
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    aria-label={t('form.isActiveLabel')}
                  />
                </FormControl>
              </FormItem>
            )}
          />

          <div className="flex items-center justify-end gap-2 pt-2">
            {mutation.isSuccess && !mutation.isPending && (
              <span className="flex items-center gap-1 text-xs text-emerald-600">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {t('form.savedJustNow')}
              </span>
            )}
            {mutation.isError && !mutation.isPending && (
              <span className="flex items-center gap-1 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5" />
                {t('form.saveError')}
              </span>
            )}
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('form.saving')}
                </>
              ) : (
                <>
                  <Database className="mr-2 h-4 w-4" />
                  {t('form.save')}
                </>
              )}
            </Button>
          </div>
        </form>
      </Form>
    </div>
  )
}
