/**
 * Backend Unavailable Alert Component
 * Displays a warning when backend API is not available with i18n support
 *
 * @module modules/admin/components
 * @author Claude Code
 * @date 2025-11-24
 */

'use client'

import { useTranslations } from 'next-intl'
import { Server } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function BackendUnavailableAlert() {
  const t = useTranslations('admin.users')

  return (
    <Alert variant="warning" className="mb-6">
      <Server className="h-4 w-4" />
      <AlertTitle>{t('backendUnavailableTitle')}</AlertTitle>
      <AlertDescription>
        <p className="mb-2">{t('backendUnavailableDescription')}</p>
        <ul className="list-disc list-inside space-y-1 text-sm">
          <li>{t('backendUnavailableReason1')}</li>
          <li>{t('backendUnavailableReason2')}</li>
          <li>{t('backendUnavailableReason3')}</li>
        </ul>
        <p className="mt-3 text-sm font-medium">
          {t('backendUnavailableInstructions')}
        </p>
      </AlertDescription>
    </Alert>
  )
}
