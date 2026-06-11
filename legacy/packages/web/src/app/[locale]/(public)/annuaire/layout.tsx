import { getTranslations } from 'next-intl/server'
import type { Metadata } from 'next'

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string }
}): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: 'public' })

  return {
    title: t('annuaire.metaTitle'),
    description: t('annuaire.metaDescription'),
    openGraph: {
      title: t('annuaire.metaTitle'),
      description: t('annuaire.metaDescription'),
      type: 'website',
    },
    alternates: {
      canonical: `/${locale}/annuaire`,
      languages: {
        es: '/es/annuaire',
        fr: '/fr/annuaire',
        en: '/en/annuaire',
      },
    },
  }
}

export default function AnnuaireLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}
