'use client'

import { useTranslations } from 'next-intl'
import { FileText } from 'lucide-react'

export default function TermsPage() {
  const t = useTranslations('legalPages')

  const sections = [
    { title: t('terms.acceptanceTitle'), content: t('terms.acceptanceContent') },
    { title: t('terms.servicesTitle'), content: t('terms.servicesContent') },
    { title: t('terms.accountTitle'), content: t('terms.accountContent') },
    { title: t('terms.obligationsTitle'), content: t('terms.obligationsContent') },
    { title: t('terms.intellectualPropertyTitle'), content: t('terms.intellectualPropertyContent') },
    { title: t('terms.limitationsTitle'), content: t('terms.limitationsContent') },
    { title: t('terms.modificationsTitle'), content: t('terms.modificationsContent') },
    { title: t('terms.jurisdictionTitle'), content: t('terms.jurisdictionContent') },
  ]

  return (
    <div className="container mx-auto max-w-4xl px-4 py-12">
      <div className="flex items-center gap-3 mb-8">
        <FileText className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold">{t('terms.title')}</h1>
      </div>
      <p className="text-muted-foreground mb-8">{t('terms.lastUpdated')}</p>
      <p className="text-lg mb-10">{t('terms.intro')}</p>

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
