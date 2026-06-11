"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useLocale, useTranslations } from "next-intl"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog"
import {
  Plus, Pencil, Trash2, RefreshCw,
  ChevronLeft, ChevronRight,
} from "lucide-react"
import FiscalServicesTabNav from "@/modules/fiscal-services/components/FiscalServicesTabNav"
import { SortableHeader } from "@/components/ui/sortable-header"
import { useSortState } from "@/hooks/use-sort-state"
import { useToast } from "@/hooks/use-toast"
import { configRulesApi, configRulesAdminApi } from "@/modules/fiscal-services/services/config-rules-api"
import { bundleApi } from "@/modules/fiscal-services/services/bundle-api"
import type {
  ConfigRuleResponse, ConfigRuleListResponse, ConfigType,
  ConfigRuleCreateInput, ConfigRuleUpdateInput,
} from "@/types/config-rule"
import type { ServiceBundle } from "@/types/service-bundle"

const CONFIG_TYPE_COLORS: Record<ConfigType, string> = {
  penalty: "bg-red-100 text-red-800",
  deadline: "bg-blue-100 text-blue-800",
  installment: "bg-amber-100 text-amber-800",
  processing_mode: "bg-purple-100 text-purple-800",
}

const PAGE_SIZE = 50

function getMonthNames(locale: string): string[] {
  const intlLocale = locale === "fr" ? "fr-FR" : locale === "en" ? "en-US" : "es-ES"
  const formatter = new Intl.DateTimeFormat(intlLocale, { month: "long" })
  return ["", ...Array.from({ length: 12 }, (_, i) => {
    const name = formatter.format(new Date(2026, i, 1))
    return name.charAt(0).toUpperCase() + name.slice(1)
  })]
}

export default function ConfigRulesPage() {
  const locale = useLocale()
  const t = useTranslations("admin.configRules")
  const { toast } = useToast()
  const monthNames = getMonthNames(locale)

  const [sort, handleSort, sortData] = useSortState()
  const [data, setData] = useState<ConfigRuleListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [configTypeFilter, setConfigTypeFilter] = useState<string>("all")
  const [bundleFilter, setBundleFilter] = useState<string>("all")
  const [enabledFilter, setEnabledFilter] = useState<string>("all")
  const [bundles, setBundles] = useState<ServiceBundle[]>([])
  const fetchSeq = useRef(0)

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingRule, setEditingRule] = useState<ConfigRuleResponse | null>(null)
  const [saving, setSaving] = useState(false)

  // Form state
  const [formConfigType, setFormConfigType] = useState<ConfigType>("penalty")
  const [formBundleId, setFormBundleId] = useState("__global__")
  const [formFeeType, setFormFeeType] = useState("__global__")
  const [formMinistryId, setFormMinistryId] = useState("")
  const [formItemId, setFormItemId] = useState("")
  const [formNameEs, setFormNameEs] = useState("")
  const [formDescription, setFormDescription] = useState("")
  const [formEnabled, setFormEnabled] = useState(true)
  const [formEffectiveFrom, setFormEffectiveFrom] = useState("")
  const [formEffectiveTo, setFormEffectiveTo] = useState("")
  // Penalty
  const [penaltyRate, setPenaltyRate] = useState("0")
  const [penaltyGraceDays, setPenaltyGraceDays] = useState("0")
  const [penaltyMaxRate, setPenaltyMaxRate] = useState("0")
  const [penaltyType, setPenaltyType] = useState("percentage")
  // Deadline
  const [deadlineMonth, setDeadlineMonth] = useState("4")
  const [deadlineDay, setDeadlineDay] = useState("30")
  // Installment
  const [installmentMax, setInstallmentMax] = useState("1")
  const [installmentFrequency, setInstallmentFrequency] = useState("monthly")
  const [installmentMinAmount, setInstallmentMinAmount] = useState("10000")
  // Processing mode
  const [processingMode, setProcessingMode] = useState("per_line")

  // Recompute state
  const [recomputeBundle, setRecomputeBundle] = useState("")
  const [recomputing, setRecomputing] = useState(false)

  useEffect(() => {
    bundleApi.listBundles({ pageSize: 100, isActive: true })
      .then(res => setBundles(res.items))
      .catch(() => {})
  }, [])

  const fetchRules = useCallback(async () => {
    const seq = ++fetchSeq.current
    setLoading(true)
    try {
      const result = await configRulesApi.listRules({
        page,
        pageSize: PAGE_SIZE,
        configType: configTypeFilter === "all" ? undefined : configTypeFilter,
        bundleId: bundleFilter === "all" ? undefined : bundleFilter,
        isEnabled: enabledFilter === "all" ? undefined : enabledFilter === "true",
      })
      if (seq === fetchSeq.current) setData(result)
    } catch {
      if (seq === fetchSeq.current) {
        toast({ variant: "destructive", title: t("loadError") })
      }
    } finally {
      if (seq === fetchSeq.current) setLoading(false)
    }
  }, [page, configTypeFilter, bundleFilter, enabledFilter, t, toast])

  useEffect(() => { fetchRules() }, [fetchRules])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0

  // Compute specificity from form
  const computeSpecificity = () => {
    let s = 0
    if (formBundleId && formBundleId !== "__global__") s += 10
    if (formFeeType && formFeeType !== "__global__") s += 20
    if (formMinistryId) s += 30
    if (formItemId) s += 50
    return s
  }

  // Build scope display
  const renderScope = (rule: ConfigRuleResponse) => {
    const parts: string[] = []
    if (rule.bundleId) parts.push(`${t("scopeBundle")}: ${rule.bundleName || rule.bundleId.slice(0, 8)}`)
    if (rule.feeType) parts.push(`${t("scopeFeeType")}: ${rule.feeType}`)
    if (rule.ministryId) parts.push(`${t("scopeMinistry")}: ${rule.ministryName || rule.ministryId}`)
    if (rule.itemId) parts.push(`${t("scopeItem")}: ${rule.itemId.slice(0, 8)}`)
    return parts.length ? parts.join(" → ") : t("scopeGlobal")
  }

  // Build config JSON from form
  const buildConfig = (): Record<string, unknown> => {
    switch (formConfigType) {
      case "penalty":
        return {
          rate: Number(penaltyRate),
          grace_days: Number(penaltyGraceDays),
          max_rate: Number(penaltyMaxRate),
          type: penaltyType,
        }
      case "deadline":
        return {
          month: Number(deadlineMonth),
          day: Number(deadlineDay),
          type: "fixed_date",
        }
      case "installment":
        return {
          max_installments: Number(installmentMax),
          frequency: installmentFrequency,
          min_amount: Number(installmentMinAmount),
        }
      case "processing_mode":
        return { mode: processingMode }
      default:
        return {}
    }
  }

  // Populate form from rule (for edit)
  const populateForm = (rule: ConfigRuleResponse) => {
    setFormConfigType(rule.configType as ConfigType)
    setFormBundleId(rule.bundleId || "__global__")
    setFormFeeType(rule.feeType || "__global__")
    setFormMinistryId(rule.ministryId ? String(rule.ministryId) : "")
    setFormItemId(rule.itemId || "")
    setFormNameEs(rule.nameEs || "")
    setFormDescription(rule.description || "")
    setFormEnabled(rule.isEnabled)
    setFormEffectiveFrom(rule.effectiveFrom || "")
    setFormEffectiveTo(rule.effectiveTo || "")

    const cfg = rule.config || {}
    switch (rule.configType) {
      case "penalty":
        setPenaltyRate(String(cfg.rate ?? 0))
        setPenaltyGraceDays(String(cfg.graceDays ?? 0))
        setPenaltyMaxRate(String(cfg.maxRate ?? 0))
        setPenaltyType(String(cfg.type ?? "percentage"))
        break
      case "deadline":
        setDeadlineMonth(String(cfg.month ?? 4))
        setDeadlineDay(String(cfg.day ?? 30))
        break
      case "installment":
        setInstallmentMax(String(cfg.maxInstallments ?? 1))
        setInstallmentFrequency(String(cfg.frequency ?? "monthly"))
        setInstallmentMinAmount(String(cfg.minAmount ?? 10000))
        break
      case "processing_mode":
        setProcessingMode(String(cfg.mode ?? "per_line"))
        break
    }
  }

  const resetForm = () => {
    setEditingRule(null)
    setFormConfigType("penalty")
    setFormBundleId("__global__")
    setFormFeeType("__global__")
    setFormMinistryId("")
    setFormItemId("")
    setFormNameEs("")
    setFormDescription("")
    setFormEnabled(true)
    setFormEffectiveFrom("")
    setFormEffectiveTo("")
    setPenaltyRate("0")
    setPenaltyGraceDays("0")
    setPenaltyMaxRate("0")
    setPenaltyType("percentage")
    setDeadlineMonth("4")
    setDeadlineDay("30")
    setInstallmentMax("1")
    setInstallmentFrequency("monthly")
    setInstallmentMinAmount("10000")
    setProcessingMode("per_line")
  }

  const handleOpenCreate = () => {
    resetForm()
    setDialogOpen(true)
  }

  const handleOpenEdit = (rule: ConfigRuleResponse) => {
    try {
      populateForm(rule)
      setEditingRule(rule)
      setDialogOpen(true)
    } catch (err) {
      console.error('[ConfigRules] Edit failed:', err, 'Rule:', JSON.stringify(rule))
      toast({ variant: 'destructive', title: 'Error al abrir edición', description: String(err) })
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      if (editingRule) {
        const updateData: ConfigRuleUpdateInput = {
          isEnabled: formEnabled,
          config: buildConfig(),
          nameEs: formNameEs || undefined,
          description: formDescription || undefined,
          effectiveFrom: formEffectiveFrom || undefined,
          effectiveTo: formEffectiveTo || undefined,
        }
        await configRulesAdminApi.updateRule(editingRule.id, updateData)
        toast({ title: t("updateSuccess") })
      } else {
        const createData: ConfigRuleCreateInput = {
          configType: formConfigType,
          bundleId: formBundleId && formBundleId !== "__global__" ? formBundleId : undefined,
          feeType: formFeeType && formFeeType !== "__global__" ? formFeeType : undefined,
          ministryId: formMinistryId ? Number(formMinistryId) : undefined,
          itemId: formItemId || undefined,
          isEnabled: formEnabled,
          config: buildConfig(),
          nameEs: formNameEs || undefined,
          description: formDescription || undefined,
          effectiveFrom: formEffectiveFrom || undefined,
          effectiveTo: formEffectiveTo || undefined,
        }
        await configRulesAdminApi.createRule(createData)
        toast({ title: t("createSuccess") })
      }
      setDialogOpen(false)
      resetForm()
      fetchRules()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : editingRule ? t("updateError") : t("createError")
      toast({ variant: "destructive", title: editingRule ? t("updateError") : t("createError"), description: msg })
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (rule: ConfigRuleResponse) => {
    if (!window.confirm(t("deleteConfirm"))) return
    try {
      await configRulesAdminApi.deleteRule(rule.id)
      toast({ title: t("deleteSuccess") })
      fetchRules()
    } catch {
      toast({ variant: "destructive", title: t("deleteError") })
    }
  }

  const handleRecompute = async () => {
    setRecomputing(true)
    try {
      const result = await configRulesAdminApi.recompute(recomputeBundle || undefined)
      toast({ title: t("recomputeSuccess", { count: result.affectedItems }) })
    } catch {
      toast({ variant: "destructive", title: t("recomputeError") })
    } finally {
      setRecomputing(false)
    }
  }

  const configTypeLabel = (ct: string) => {
    const key = `type${ct.split("_").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join("")}` as string
    try { return t(key as Parameters<typeof t>[0]) } catch { return ct }
  }

  return (
    <div className="space-y-4 p-4">
      <FiscalServicesTabNav activeTab="config" />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="flex gap-2">
          {/* Recompute */}
          <div className="flex items-center gap-1">
            <Select value={recomputeBundle || "all"} onValueChange={v => setRecomputeBundle(v === "all" ? "" : v)}>
              <SelectTrigger className="w-[130px] h-9"><SelectValue placeholder={t("allBundles")} /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("allBundles")}</SelectItem>
                {bundles.map(b => <SelectItem key={b.id} value={b.id}>{b.bundleCode}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" onClick={handleRecompute} disabled={recomputing}>
              <RefreshCw className={`h-3.5 w-3.5 mr-1 ${recomputing ? "animate-spin" : ""}`} />
              {t("recompute")}
            </Button>
          </div>
          <Button size="sm" onClick={handleOpenCreate}>
            <Plus className="h-4 w-4 mr-1" /> {t("newRule")}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select value={configTypeFilter} onValueChange={v => { setConfigTypeFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[160px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allTypes")}</SelectItem>
            {(["penalty", "deadline", "installment", "processing_mode"] as ConfigType[]).map(ct => (
              <SelectItem key={ct} value={ct}>{configTypeLabel(ct)}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={bundleFilter} onValueChange={v => { setBundleFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[180px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allBundles")}</SelectItem>
            {bundles.map(b => <SelectItem key={b.id} value={b.id}>{b.bundleCode}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={enabledFilter} onValueChange={v => { setEnabledFilter(v); setPage(1) }}>
          <SelectTrigger className="w-[130px] h-9"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStatuses")}</SelectItem>
            <SelectItem value="true">{t("enabled")}</SelectItem>
            <SelectItem value="false">{t("disabled")}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <SortableHeader column="nameEs" label={t("name")} sort={sort} onSort={handleSort} />
              <SortableHeader column="configType" label={t("configType")} sort={sort} onSort={handleSort} className="w-[110px]" />
              <TableHead>{t("scope")}</TableHead>
              <SortableHeader column="specificity" label={t("specificity")} sort={sort} onSort={handleSort} className="w-[90px] text-center" />
              <SortableHeader column="effectiveFrom" label={t("effectivePeriod")} sort={sort} onSort={handleSort} className="w-[150px]" />
              <SortableHeader column="isEnabled" label={t("isEnabled")} sort={sort} onSort={handleSort} className="w-[80px] text-center" />
              <TableHead className="w-[80px]">{t("actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">{t("loading")}</TableCell>
              </TableRow>
            ) : !data?.items?.length ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">{t("noResults")}</TableCell>
              </TableRow>
            ) : (sortData(data.items as unknown as Record<string, unknown>[], { nameEs: 'string', configType: 'string', specificity: 'number', effectiveFrom: 'date', isEnabled: 'boolean' }) as unknown as typeof data.items).map(rule => (
              <TableRow key={rule.id} className="hover:bg-muted/50">
                <TableCell className="text-sm">{rule.nameEs || "—"}</TableCell>
                <TableCell>
                  <Badge className={`text-xs ${CONFIG_TYPE_COLORS[rule.configType as ConfigType] || ""}`} variant="secondary">
                    {configTypeLabel(rule.configType)}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs max-w-[250px] truncate">{renderScope(rule)}</TableCell>
                <TableCell className="text-center font-mono text-sm font-bold">{rule.specificity}</TableCell>
                <TableCell className="text-xs">
                  {rule.effectiveFrom}
                  {rule.effectiveTo ? ` → ${rule.effectiveTo}` : ` → ${t("noExpiration")}`}
                </TableCell>
                <TableCell className="text-center">
                  <Badge variant={rule.isEnabled ? "default" : "secondary"} className="text-xs">
                    {rule.isEnabled ? t("enabled") : t("disabled")}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex gap-0.5">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleOpenEdit(rule)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={() => handleDelete(rule)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {t("pageInfo", { total: data?.total ?? 0, page, totalPages })}
          </span>
          <div className="flex gap-1">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={v => { if (!v) resetForm(); setDialogOpen(v) }}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingRule ? t("editTitle") : t("createTitle")}</DialogTitle>
            <DialogDescription>{t("createDesc")}</DialogDescription>
          </DialogHeader>

          <div className="space-y-5 py-2">
            {/* Section 1: Identity */}
            <div className="space-y-3">
              <h4 className="text-sm font-bold text-muted-foreground">{t("sectionIdentity")}</h4>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>{t("ruleName")}</Label>
                  <Input value={formNameEs} onChange={e => setFormNameEs(e.target.value)} placeholder={t("ruleNameHint")} />
                </div>
                <div className="space-y-1">
                  <Label>{t("configType")}</Label>
                  <Select value={formConfigType} onValueChange={v => setFormConfigType(v as ConfigType)} disabled={!!editingRule}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(["penalty", "deadline", "installment", "processing_mode"] as ConfigType[]).map(ct => (
                        <SelectItem key={ct} value={ct}>{configTypeLabel(ct)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1">
                <Label>{t("ruleDescription")}</Label>
                <Textarea value={formDescription} onChange={e => setFormDescription(e.target.value)} rows={2} />
              </div>
              <div className="flex items-center gap-2">
                <Switch checked={formEnabled} onCheckedChange={setFormEnabled} />
                <Label>{formEnabled ? t("enabled") : t("disabled")}</Label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>{t("effectiveFrom")}</Label>
                  <Input type="date" value={formEffectiveFrom} onChange={e => setFormEffectiveFrom(e.target.value)} />
                </div>
                <div className="space-y-1">
                  <Label>{t("effectiveTo")}</Label>
                  <Input type="date" value={formEffectiveTo} onChange={e => setFormEffectiveTo(e.target.value)} placeholder={t("noExpiration")} />
                </div>
              </div>
            </div>

            {/* Section 2: Scope */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-muted-foreground">{t("sectionScope")}</h4>
                <Badge variant="outline" className="text-xs font-mono">
                  {t("liveSpecificity", { value: computeSpecificity() })}
                </Badge>
              </div>
              {editingRule && (
                <p className="text-xs text-amber-600">{t("scopeImmutable")}</p>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label>{t("scopeBundle")} (+10)</Label>
                  <Select value={formBundleId} onValueChange={setFormBundleId} disabled={!!editingRule}>
                    <SelectTrigger><SelectValue placeholder={t("selectBundle")} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__global__">{t("scopeGlobal")}</SelectItem>
                      {bundles.map(b => <SelectItem key={b.id} value={b.id}>{b.bundleCode}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>{t("scopeFeeType")} (+20)</Label>
                  <Select value={formFeeType} onValueChange={setFormFeeType} disabled={!!editingRule}>
                    <SelectTrigger><SelectValue placeholder={t("selectFeeType")} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__global__">{t("scopeGlobal")}</SelectItem>
                      <SelectItem value="tesoro">Tesoro</SelectItem>
                      <SelectItem value="municipal">Municipal</SelectItem>
                      <SelectItem value="chamber">Chamber</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>{t("scopeMinistry")} (+30)</Label>
                  <Input
                    value={formMinistryId} onChange={e => setFormMinistryId(e.target.value)}
                    placeholder="Ministry ID" type="number" disabled={!!editingRule}
                  />
                </div>
                <div className="space-y-1">
                  <Label>{t("scopeItem")} (+50)</Label>
                  <Input
                    value={formItemId} onChange={e => setFormItemId(e.target.value)}
                    placeholder="Item UUID" disabled={!!editingRule}
                  />
                </div>
              </div>
            </div>

            {/* Section 3: Config JSON Builder */}
            <div className="space-y-3">
              <h4 className="text-sm font-bold text-muted-foreground">{t("sectionConfig")}</h4>

              {formConfigType === "penalty" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>{t("penaltyRate")}</Label>
                    <Input type="number" step="0.01" min="0" value={penaltyRate} onChange={e => setPenaltyRate(e.target.value)} />
                    <p className="text-xs text-muted-foreground">{t("penaltyRateHint")}</p>
                  </div>
                  <div className="space-y-1">
                    <Label>{t("penaltyGraceDays")}</Label>
                    <Input type="number" min="0" value={penaltyGraceDays} onChange={e => setPenaltyGraceDays(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>{t("penaltyMaxRate")}</Label>
                    <Input type="number" step="0.01" min="0" value={penaltyMaxRate} onChange={e => setPenaltyMaxRate(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>{t("penaltyType")}</Label>
                    <Select value={penaltyType} onValueChange={setPenaltyType}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percentage">{t("penaltyTypePercentage")}</SelectItem>
                        <SelectItem value="flat">{t("penaltyTypeFlat")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              {formConfigType === "deadline" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label>{t("deadlineMonth")}</Label>
                      <Select value={deadlineMonth} onValueChange={setDeadlineMonth}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
                            <SelectItem key={m} value={String(m)}>{monthNames[m]}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label>{t("deadlineDay")}</Label>
                      <Select value={deadlineDay} onValueChange={setDeadlineDay}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 31 }, (_, i) => i + 1).map(d => (
                            <SelectItem key={d} value={String(d)}>{d}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {t("deadlinePreview", { date: `${monthNames[Number(deadlineMonth)]} ${deadlineDay}` })}
                  </p>
                </div>
              )}

              {formConfigType === "installment" && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>{t("installmentMax")}</Label>
                    <Input type="number" min="1" value={installmentMax} onChange={e => setInstallmentMax(e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>{t("installmentFrequency")}</Label>
                    <Select value={installmentFrequency} onValueChange={setInstallmentFrequency}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="monthly">{t("installmentFreqMonthly")}</SelectItem>
                        <SelectItem value="bi-monthly">{t("installmentFreqBimonthly")}</SelectItem>
                        <SelectItem value="quarterly">{t("installmentFreqQuarterly")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1 col-span-2">
                    <Label>{t("installmentMinAmount")}</Label>
                    <Input type="number" min="0" value={installmentMinAmount} onChange={e => setInstallmentMinAmount(e.target.value)} />
                  </div>
                </div>
              )}

              {formConfigType === "processing_mode" && (
                <div className="space-y-1">
                  <Label>{t("processingModeLabel")}</Label>
                  <Select value={processingMode} onValueChange={setProcessingMode}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="per_line">{t("processingModePerLine")}</SelectItem>
                      <SelectItem value="consolidated">{t("processingModeConsolidated")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? t("saving") : t("save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
