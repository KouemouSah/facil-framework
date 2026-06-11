'use client'

import { useEffect } from 'react'
import { useLocale } from 'next-intl'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

const texts = {
  es: { title: 'Error inesperado', subtitle: 'Se produjo un error. Por favor intente de nuevo.', retry: 'Reintentar', home: 'Inicio' },
  fr: { title: 'Erreur inattendue', subtitle: 'Une erreur s\'est produite. Veuillez reessayer.', retry: 'Reessayer', home: 'Accueil' },
  en: { title: 'Unexpected error', subtitle: 'An error occurred. Please try again.', retry: 'Retry', home: 'Home' },
} as const

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const locale = useLocale()
  const t = texts[locale as keyof typeof texts] || texts.es

  useEffect(() => {
    console.error('[Dashboard Error Boundary]', error)
  }, [error])

  return (
    <div className="flex items-center justify-center min-h-[60vh] p-6">
      <Card className="max-w-md w-full">
        <CardContent className="pt-6 text-center space-y-4">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto" />
          <h2 className="text-lg font-semibold">{t.title}</h2>
          <p className="text-sm text-muted-foreground">{t.subtitle}</p>
          {error.digest && (
            <p className="text-xs text-muted-foreground font-mono">Ref: {error.digest}</p>
          )}
          <div className="flex gap-2 justify-center">
            <Button onClick={reset} variant="default" className="gap-2">
              <RefreshCw className="h-4 w-4" />
              {t.retry}
            </Button>
            <Button onClick={() => window.location.href = '/'} variant="outline" className="gap-2">
              <Home className="h-4 w-4" />
              {t.home}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
