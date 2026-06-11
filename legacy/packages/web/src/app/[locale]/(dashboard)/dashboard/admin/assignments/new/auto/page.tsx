'use client'

/**
 * Auto Assignment Creation Page
 * Allows admin/supervisor to trigger automatic assignment using intelligent algorithm
 *
 * ARCHITECTURE NOTE:
 * The auto-assignment algorithm considers:
 * - Agent workloads and availability
 * - Specializations matching item type
 * - Performance history (speed, success rate)
 * - Configured assignment rules
 *
 * In production, auto-assign should typically be triggered automatically
 * when items enter the queue, not manually from this page.
 *
 * @route /[locale]/dashboard/admin/assignments/new/auto
 * @date 2026-01-23
 */

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useLocale, useTranslations } from 'next-intl'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ArrowLeft, Loader2, Zap, FileText, Info, Building2 } from 'lucide-react'
import { toast } from 'sonner'
import { assignmentsApi } from '@/modules/assignments-admin/services/api'
import type { ItemType } from '@/modules/assignments-admin/types'
import { useQuery } from '@tanstack/react-query'
import { fetchClient } from '@/core/api'

// Item types that can be assigned - aligned with ItemType
const ITEM_TYPES: { value: ItemType; label: string }[] = [
  { value: 'service_request', label: 'Service Request' },
  { value: 'tax_declaration', label: 'Tax Declaration' },
  { value: 'service_payment', label: 'Service Payment' },
  { value: 'other', label: 'Other' },
]

// Entity types - aligned with backend pattern: ^(ministry|entity)$
const ENTITY_TYPES = [
  { value: 'ministry', label: 'Ministry' },
  { value: 'entity', label: 'Entity' },
] as const

type EntityType = 'ministry' | 'entity'

interface Ministry {
  id: number
  name: string
  name_es?: string
}

interface Entity {
  id: string
  name: string
  name_es?: string
}

export default function AutoAssignmentPage() {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations('admin.assignments')
  const tCommon = useTranslations('common')

  // Form state
  const [itemId, setItemId] = useState('')
  const [itemType, setItemType] = useState<ItemType | ''>('')
  const [entityType, setEntityType] = useState<EntityType>('ministry')
  const [ministryId, setMinistryId] = useState<number | null>(null)
  const [entityId, setEntityId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch ministries
  const { data: ministries = [] } = useQuery({
    queryKey: ['ministries'],
    queryFn: async () => {
      const response = await fetchClient.get<{ items: Ministry[] }>('/ministries/')
      return response.items || []
    },
  })

  // Fetch entities (if entity type selected)
  const { data: entities = [] } = useQuery({
    queryKey: ['entities'],
    queryFn: async () => {
      const response = await fetchClient.get<{ items: Entity[] }>('/entities/')
      return response.items || []
    },
    enabled: entityType === 'entity',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!itemId || !itemType) {
      toast.error(t('fillRequiredFields'))
      return
    }

    setIsSubmitting(true)
    try {
      // Build entity_id based on selection
      const selectedEntityId =
        entityType === 'ministry' && ministryId
          ? ministryId.toString()
          : entityType === 'entity' && entityId
            ? entityId
            : undefined

      const result = await assignmentsApi.createAuto({
        item_id: itemId,
        item_type: itemType,
        item_data: {}, // Empty object - rules will evaluate based on item_type
        entity_type: entityType,
        entity_id: selectedEntityId,
      })
      toast.success(t('autoAssignmentSuccess', { agent: result.agent_name || 'agent' }))
      router.push(`/${locale}/dashboard/admin/assignments`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to auto-assign')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/${locale}/dashboard/admin/assignments`}>
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{t('autoAssignment')}</h1>
          <p className="text-muted-foreground">{t('autoAssignmentDescription')}</p>
        </div>
      </div>

      {/* Info Card */}
      <Card className="border-blue-200 bg-blue-50/50">
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p className="font-medium mb-1">{t('howAutoAssignmentWorks')}</p>
              <ul className="list-disc list-inside space-y-1 text-blue-700">
                <li>{t('autoFeature1')}</li>
                <li>{t('autoFeature2')}</li>
                <li>{t('autoFeature3')}</li>
                <li>{t('autoFeature4')}</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            {t('itemDetails')}
          </CardTitle>
          <CardDescription>{t('selectItemForAutoAssign')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Item Type */}
            <div className="space-y-2">
              <Label htmlFor="itemType">{t('itemType') || 'Item Type'} *</Label>
              <Select
                value={itemType}
                onValueChange={(value: string) => setItemType(value as ItemType)}
              >
                <SelectTrigger id="itemType">
                  <SelectValue placeholder={t('selectItemType')} />
                </SelectTrigger>
                <SelectContent>
                  {ITEM_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {t(`itemTypes.${type.value}`) || type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Item ID */}
            <div className="space-y-2">
              <Label htmlFor="itemId">{t('itemId')} *</Label>
              <Input
                id="itemId"
                placeholder={t('enterItemId')}
                value={itemId}
                onChange={(e) => setItemId(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">{t('itemIdHelp')}</p>
            </div>

            {/* Entity Type */}
            <div className="space-y-2">
              <Label htmlFor="entityType">
                <Building2 className="inline h-4 w-4 mr-1" />
                {t('entityType')}
              </Label>
              <Select
                value={entityType}
                onValueChange={(value: string) => {
                  setEntityType(value as EntityType)
                  setMinistryId(null)
                  setEntityId(null)
                }}
              >
                <SelectTrigger id="entityType">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ENTITY_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {t(`entityTypes.${type.value}`) || type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{t('entityTypeHelp')}</p>
            </div>

            {/* Ministry/Entity Selection (optional for auto-assign) */}
            {entityType === 'ministry' ? (
              <div className="space-y-2">
                <Label htmlFor="ministry">
                  {t('entityTypes.ministry')} ({tCommon('optional')})
                </Label>
                <Select
                  value={ministryId?.toString() || ''}
                  onValueChange={(value: string) =>
                    setMinistryId(value ? parseInt(value, 10) : null)
                  }
                >
                  <SelectTrigger id="ministry">
                    <SelectValue placeholder={t('entityIdHelp')} />
                  </SelectTrigger>
                  <SelectContent>
                    {ministries.map((m) => (
                      <SelectItem key={m.id} value={m.id.toString()}>
                        {m.name_es || m.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="entity">
                  {t('entityTypes.entity')} ({tCommon('optional')})
                </Label>
                <Select
                  value={entityId || ''}
                  onValueChange={(value: string) => setEntityId(value || null)}
                >
                  <SelectTrigger id="entity">
                    <SelectValue placeholder={t('entityIdHelp')} />
                  </SelectTrigger>
                  <SelectContent>
                    {entities.map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.name_es || e.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-between pt-4">
              <Link href={`/${locale}/dashboard/admin/assignments`}>
                <Button type="button" variant="outline">
                  {tCommon('cancel')}
                </Button>
              </Link>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                <Zap className="mr-2 h-4 w-4" />
                {t('runAutoAssignment')}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
