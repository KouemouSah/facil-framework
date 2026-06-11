'use client'

import { useEffect } from 'react'
import { useTranslations } from 'next-intl'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const t = useTranslations('admin')

  useEffect(() => {
    console.error('[Admin Error Boundary]', error)
  }, [error])

  return (
    <div className="flex items-center justify-center min-h-[60vh] p-6">
      <Card className="max-w-md w-full">
        <CardContent className="pt-6 text-center space-y-4">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto" />
          <h2 className="text-lg font-semibold">{t('errorBoundary.title')}</h2>
          <p className="text-sm text-muted-foreground">
            {t('errorBoundary.description')}
          </p>
          {error.digest && (
            <p className="text-xs text-muted-foreground font-mono">
              Ref: {error.digest}
            </p>
          )}
          <Button onClick={reset} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            {t('errorBoundary.retry')}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
