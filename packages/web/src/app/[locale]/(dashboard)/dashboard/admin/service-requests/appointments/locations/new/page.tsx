'use client'

import { useTranslations } from 'next-intl'
import { useRouter, useParams } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, MapPin } from 'lucide-react'
import { useCreateEntityLocation } from '@/modules/entity-locations/hooks'
import { EntityLocationForm } from '@/modules/entity-locations/components/EntityLocationForm'
import type { EntityLocationCreate } from '@/modules/entity-locations/types'
import { toast } from 'sonner'

export default function NewLocationPage() {
  const t = useTranslations('admin.serviceRequests.appointments.locations')
  const router = useRouter()
  const params = useParams()
  const locale = params.locale as string

  const createMutation = useCreateEntityLocation()

  const handleBack = () => {
    router.push(`/${locale}/dashboard/admin/service-requests/appointments?tab=locations`)
  }

  const handleCreate = async (data: EntityLocationCreate) => {
    try {
      await createMutation.mutateAsync(data)
      toast.success(t('form.createSuccess'))
      handleBack()
    } catch (error) {
      toast.error(t('form.createError'))
      console.error('Failed to create location:', error)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('form.createTitle')}</h1>
          <p className="text-muted-foreground">{t('form.createDescription')}</p>
        </div>
      </div>

      {/* Form Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            {t('form.locationDetails')}
          </CardTitle>
          <CardDescription>{t('form.locationDetailsDescription')}</CardDescription>
        </CardHeader>
        <CardContent>
          <EntityLocationForm
            onSubmit={handleCreate}
            onCancel={handleBack}
            isLoading={createMutation.isPending}
          />
        </CardContent>
      </Card>
    </div>
  )
}
