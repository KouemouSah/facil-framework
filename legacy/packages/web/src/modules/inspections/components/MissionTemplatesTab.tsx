'use client'

/**
 * MissionTemplatesTab — CRUD for recurring mission templates.
 * Create, toggle, run manually, delete templates.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import {
  Plus, Play, Trash2, RefreshCw, Clock,
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { Textarea } from '@/components/ui/textarea'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog'
import { inspectionApi } from '@/modules/inspections/services/api'
import type { MissionTemplate } from '@/modules/inspections/types'

interface Props {
  locationFilter?: string
}

const RECURRENCE_COLORS: Record<string, string> = {
  daily: 'bg-blue-100 text-blue-800',
  weekly: 'bg-green-100 text-green-800',
  biweekly: 'bg-purple-100 text-purple-800',
  monthly: 'bg-orange-100 text-orange-800',
}

const DAYS_OF_WEEK_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export function MissionTemplatesTab({ locationFilter: _locationFilter }: Props) {
  const t = useTranslations('inspection')
  const [templates, setTemplates] = useState<MissionTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)

  // Create form
  const [formName, setFormName] = useState('')
  const [formRecurrence, setFormRecurrence] = useState('weekly')
  const [formDayOfWeek, setFormDayOfWeek] = useState(0)
  const [formDayOfMonth, setFormDayOfMonth] = useState(1)
  const [formTarget, setFormTarget] = useState(10)
  const [formNotes, setFormNotes] = useState('')
  const [creating, setCreating] = useState(false)

  const fetchTemplates = useCallback(async () => {
    try {
      setLoading(true)
      const data = await inspectionApi.listTemplates()
      setTemplates(data)
    } catch {
      toast.error(t('common.error', { defaultMessage: 'Error' }))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  const handleCreate = useCallback(async () => {
    if (!formName.trim()) return
    setCreating(true)
    try {
      await inspectionApi.createTemplate({
        name: formName.trim(),
        recurrence: formRecurrence,
        day_of_week: ['weekly', 'biweekly'].includes(formRecurrence) ? formDayOfWeek : undefined,
        day_of_month: formRecurrence === 'monthly' ? formDayOfMonth : undefined,
        target_inspections_per_agent: formTarget,
        notes: formNotes.trim() || undefined,
      })
      toast.success(t('missions.templateCreated', { defaultMessage: 'Template created' }))
      setShowCreate(false)
      setFormName('')
      setFormNotes('')
      fetchTemplates()
    } catch (err) {
      toast.error(String(err))
    } finally {
      setCreating(false)
    }
  }, [formName, formRecurrence, formDayOfWeek, formDayOfMonth, formTarget, formNotes, t, fetchTemplates])

  const handleToggle = useCallback(async (tpl: MissionTemplate) => {
    try {
      await inspectionApi.updateTemplate(tpl.id, { is_active: !tpl.is_active })
      fetchTemplates()
    } catch (err) {
      toast.error(String(err))
    }
  }, [fetchTemplates])

  const handleRun = useCallback(async (tpl: MissionTemplate) => {
    setRunningId(tpl.id)
    try {
      const result = await inspectionApi.runTemplate(tpl.id)
      toast.success(
        `${t('missions.missionCreated', { defaultMessage: 'Mission created' })}: ${result.mission_date} (${result.agents_assigned} agents)`
      )
      fetchTemplates()
    } catch (err) {
      toast.error(String(err))
    } finally {
      setRunningId(null)
    }
  }, [t, fetchTemplates])

  const handleDelete = useCallback(async (id: string) => {
    try {
      await inspectionApi.deleteTemplate(id)
      toast.success(t('missions.templateDeleted', { defaultMessage: 'Template deleted' }))
      fetchTemplates()
    } catch (err) {
      toast.error(String(err))
    }
  }, [t, fetchTemplates])

  if (loading) {
    return <div className="space-y-3">{[1,2].map(i => <Skeleton key={i} className="h-24 rounded-lg" />)}</div>
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <p className="text-sm text-muted-foreground">
          {t('missions.templatesDesc', { defaultMessage: 'Recurring templates auto-create missions on schedule.' })}
        </p>
        <Button size="sm" onClick={() => setShowCreate(true)} className="gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          {t('missions.newTemplate', { defaultMessage: 'New template' })}
        </Button>
      </div>

      {/* Template list */}
      {templates.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Clock className="h-10 w-10 mx-auto mb-2 opacity-40" />
            <p>{t('missions.noTemplates', { defaultMessage: 'No templates configured' })}</p>
          </CardContent>
        </Card>
      ) : (
        templates.map((tpl) => (
          <Card key={tpl.id} className={!tpl.is_active ? 'opacity-60' : ''}>
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{tpl.name}</span>
                    <Badge className={RECURRENCE_COLORS[tpl.recurrence] ?? ''} variant="secondary">
                      {t(`missions.${tpl.recurrence}`, { defaultMessage: tpl.recurrence })}
                    </Badge>
                    {tpl.day_of_week != null && (
                      <span className="text-xs text-muted-foreground">
                        {t(`missions.days.${DAYS_OF_WEEK_KEYS[tpl.day_of_week]}`, { defaultMessage: DAYS_OF_WEEK_KEYS[tpl.day_of_week] })}
                      </span>
                    )}
                    {tpl.day_of_month != null && (
                      <span className="text-xs text-muted-foreground">
                        {t('missions.dayLabel', { defaultMessage: 'Day' })} {tpl.day_of_month}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>{tpl.target_inspections_per_agent} {t('missions.inspPerAgent', { defaultMessage: 'insp/agent' })}</span>
                    {tpl.default_agent_ids && (
                      <span>{tpl.default_agent_ids.length} {t('missions.defaultAgentsLabel', { defaultMessage: 'agents' })}</span>
                    )}
                    {tpl.zone_ids && (
                      <span>{tpl.zone_ids.length} {t('missions.zonesLabel', { defaultMessage: 'zones' })}</span>
                    )}
                  </div>
                  {tpl.last_created_at && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {t('missions.lastRun', { defaultMessage: 'Last run' })}: {new Date(tpl.last_created_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={tpl.is_active}
                    onCheckedChange={() => handleToggle(tpl)}
                    title={tpl.is_active ? 'Active' : 'Inactive'}
                  />
                  <Button
                    size="sm" variant="outline" className="gap-1"
                    onClick={() => handleRun(tpl)}
                    disabled={!tpl.is_active || runningId === tpl.id}
                  >
                    {runningId === tpl.id ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3" />}
                    {t('missions.runNow', { defaultMessage: 'Run' })}
                  </Button>
                  <Button
                    size="icon" variant="ghost" className="h-8 w-8"
                    onClick={() => handleDelete(tpl.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('missions.newTemplate', { defaultMessage: 'New template' })}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{t('common.name', { defaultMessage: 'Name' })}</Label>
              <Input value={formName} onChange={e => setFormName(e.target.value)} placeholder="ex: Mission hebdo zone A1" />
            </div>
            <div>
              <Label>{t('missions.recurrence', { defaultMessage: 'Recurrence' })}</Label>
              <Select value={formRecurrence} onValueChange={setFormRecurrence}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">{t('missions.daily', { defaultMessage: 'Daily' })}</SelectItem>
                  <SelectItem value="weekly">{t('missions.weekly', { defaultMessage: 'Weekly' })}</SelectItem>
                  <SelectItem value="biweekly">{t('missions.biweekly', { defaultMessage: 'Biweekly' })}</SelectItem>
                  <SelectItem value="monthly">{t('missions.monthly', { defaultMessage: 'Monthly' })}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {['weekly', 'biweekly'].includes(formRecurrence) && (
              <div>
                <Label>{t('missions.dayOfWeek', { defaultMessage: 'Day of week' })}</Label>
                <Select value={String(formDayOfWeek)} onValueChange={v => setFormDayOfWeek(Number(v))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {DAYS_OF_WEEK_KEYS.map((day, i) => (
                      <SelectItem key={i} value={String(i)}>{t(`missions.days.${day}`, { defaultMessage: day })}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {formRecurrence === 'monthly' && (
              <div>
                <Label>{t('missions.dayOfMonth', { defaultMessage: 'Day of month' })}</Label>
                <Input type="number" min={1} max={28} value={formDayOfMonth} onChange={e => setFormDayOfMonth(Number(e.target.value))} />
              </div>
            )}
            <div>
              <Label>{t('missions.targetPerAgent', { defaultMessage: 'Target per agent' })}</Label>
              <Input type="number" min={1} max={100} value={formTarget} onChange={e => setFormTarget(Number(e.target.value))} />
            </div>
            <div>
              <Label>{t('inspection.notes', { defaultMessage: 'Notes' })}</Label>
              <Textarea value={formNotes} onChange={e => setFormNotes(e.target.value)} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>{t('common.cancel', { defaultMessage: 'Cancel' })}</Button>
            <Button onClick={handleCreate} disabled={creating || !formName.trim()}>
              {creating ? <RefreshCw className="h-3.5 w-3.5 animate-spin mr-1" /> : <Plus className="h-3.5 w-3.5 mr-1" />}
              {t('common.create', { defaultMessage: 'Create' })}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
