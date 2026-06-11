"use client"

import { useRouter } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { FileText, Package, FolderOpen, Cog } from "lucide-react"
import { cn } from "@/core/utils"

export type FiscalTab = "catalog" | "bundles" | "licenses" | "config"

const TABS: { id: FiscalTab; icon: typeof FileText; labelKey: string; path: string }[] = [
  { id: "catalog", icon: FileText, labelKey: "services", path: "fiscal-services" },
  { id: "bundles", icon: Package, labelKey: "tabBundles", path: "service-bundles" },
  { id: "licenses", icon: FolderOpen, labelKey: "tabLicenses", path: "licenses" },
  { id: "config", icon: Cog, labelKey: "tabConfig", path: "config-rules" },
]

interface FiscalServicesTabNavProps {
  activeTab: FiscalTab
}

export default function FiscalServicesTabNav({ activeTab }: FiscalServicesTabNavProps) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("admin.serviceBundles")

  return (
    <div className="flex gap-1 border-b">
      {TABS.map(({ id, icon: Icon, labelKey, path }) => {
        const isActive = id === activeTab
        return (
          <button
            key={id}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
              isActive
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
            onClick={isActive ? undefined : () => router.push(`/${locale}/dashboard/admin/${path}`)}
          >
            <Icon className="h-3.5 w-3.5 inline mr-1" />
            {t(labelKey as Parameters<typeof t>[0])}
          </button>
        )
      })}
    </div>
  )
}
