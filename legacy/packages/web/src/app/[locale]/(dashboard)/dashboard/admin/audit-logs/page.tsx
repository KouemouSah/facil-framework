'use client'

import { useTranslations } from 'next-intl'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileText, Cpu } from 'lucide-react'
import { AuditLogsTab } from '@/modules/audit-logs-admin/components/AuditLogsTab'
import { GeminiCostsTab } from '@/modules/audit-logs-admin/components/GeminiCostsTab'

export default function AuditLogsPage() {
  const t = useTranslations('admin.auditLogs')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
        <p className="text-muted-foreground">{t('subtitle')}</p>
      </div>

      <Tabs defaultValue="logs">
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="logs" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            {t('tabActivity')}
          </TabsTrigger>
          <TabsTrigger value="gemini" className="flex items-center gap-2">
            <Cpu className="h-4 w-4" />
            {t('tabGeminiCosts')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="logs" className="mt-4">
          <AuditLogsTab />
        </TabsContent>

        <TabsContent value="gemini" className="mt-4">
          <GeminiCostsTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}
