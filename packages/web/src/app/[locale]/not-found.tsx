'use client'

import Link from 'next/link'
import { FileQuestion, Home, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useLocale } from 'next-intl'

const texts = {
  es: { title: 'Pagina no encontrada', subtitle: 'La pagina que busca no existe o ha sido movida.', home: 'Inicio', back: 'Volver' },
  fr: { title: 'Page non trouvee', subtitle: 'La page que vous recherchez n\'existe pas ou a ete deplacee.', home: 'Accueil', back: 'Retour' },
  en: { title: 'Page not found', subtitle: 'The page you are looking for does not exist or has been moved.', home: 'Home', back: 'Back' },
} as const

export default function NotFound() {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const locale = useLocale()
  const t = texts[locale as keyof typeof texts] || texts.es

  return (
    <div className="flex items-center justify-center min-h-screen p-6">
      <div className="max-w-md w-full text-center space-y-6">
        <FileQuestion className="h-16 w-16 text-muted-foreground mx-auto" />
        <div className="space-y-2">
          <h1 className="text-4xl font-bold">404</h1>
          <h2 className="text-lg font-semibold">{t.title}</h2>
          <p className="text-sm text-muted-foreground">{t.subtitle}</p>
        </div>
        <div className="flex gap-3 justify-center">
          <Button asChild variant="default" className="gap-2">
            <Link href="/">
              <Home className="h-4 w-4" />
              {t.home}
            </Link>
          </Button>
          <Button onClick={() => typeof window !== 'undefined' && window.history.back()} variant="outline" className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            {t.back}
          </Button>
        </div>
      </div>
    </div>
  )
}
