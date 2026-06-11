'use client'

import { useTranslations } from 'next-intl'
import { Shield } from 'lucide-react'

export default function PrivacyPage() {
  const t = useTranslations('legalPages')

  const sections = [
    { title: t('privacy.dataCollectedTitle'), content: t('privacy.dataCollectedContent') },
    { title: t('privacy.purposeTitle'), content: t('privacy.purposeContent') },
    { title: t('privacy.legalBasisTitle'), content: t('privacy.legalBasisContent') },
    { title: t('privacy.retentionTitle'), content: t('privacy.retentionContent') },
    { title: t('privacy.sharingTitle'), content: t('privacy.sharingContent') },
    { title: t('privacy.rightsTitle'), content: t('privacy.rightsContent') },
    { title: t('privacy.securityTitle'), content: t('privacy.securityContent') },
    { title: t('privacy.contactTitle'), content: t('privacy.contactContent') },
  ]

  return (
    <div className="container mx-auto max-w-4xl px-4 py-12">
      <div className="flex items-center gap-3 mb-8">
        <Shield className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold">{t('privacy.title')}</h1>
      </div>
      <p className="text-muted-foreground mb-8">{t('privacy.lastUpdated')}</p>
      <p className="text-lg mb-10">{t('privacy.intro')}</p>

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
