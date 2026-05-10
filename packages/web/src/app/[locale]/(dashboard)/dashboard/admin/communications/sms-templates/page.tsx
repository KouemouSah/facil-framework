'use client'

import { SmsTemplateList } from '@/modules/communications/components/SmsTemplateList'

interface PageProps {
  params: { locale: string }
}

export default function SmsTemplatesPage({ params }: PageProps) {
  return <SmsTemplateList locale={params.locale} />
}
