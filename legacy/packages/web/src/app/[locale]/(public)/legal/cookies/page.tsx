'use client'

import { useTranslations } from 'next-intl'
import { Cookie } from 'lucide-react'

export default function CookiesPage() {
  const t = useTranslations('legalPages')

  const sections = [
    { title: t('cookies.whatAreTitle'), content: t('cookies.whatAreContent') },
    { title: t('cookies.typesTitle'), content: t('cookies.typesContent') },
    { title: t('cookies.purposeTitle'), content: t('cookies.purposeContent') },
    { title: t('cookies.thirdPartyTitle'), content: t('cookies.thirdPartyContent') },
    { title: t('cookies.managementTitle'), content: t('cookies.managementContent') },
    { title: t('cookies.contactTitle'), content: t('cookies.contactContent') },
  ]

  return (
    <div className="container mx-auto max-w-4xl px-4 py-12">
      <div className="flex items-center gap-3 mb-8">
        <Cookie className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold">{t('cookies.title')}</h1>
      </div>
      <p className="text-muted-foreground mb-8">{t('cookies.lastUpdated')}</p>
      <p className="text-lg mb-10">{t('cookies.intro')}</p>

      <div className="space-y-8">
        {sections.map((section, i) => (
          <section key={i}>
            <h2 className="text-xl font-semibold mb-3">
              {i + 1}. {section.title}
            </h2>
            <p className="text-muted-foreground leading-relaxed whitespace-pre-line">
              {section.content}
            </p>
          </section>
        ))}
      </div>
    </div>
  )
}
