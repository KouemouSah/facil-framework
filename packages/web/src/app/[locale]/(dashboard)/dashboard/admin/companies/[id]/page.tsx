"use client"

import { useState, useEffect, useCallback } from "react"
import { useRouter, useParams } from "next/navigation"
import { useLocale, useTranslations } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table"
import {
  ArrowLeft, Building2, ShieldCheck, Users, FileText, Loader2,
  CheckCircle, XCircle, MapPin, Mail, Phone, Calendar, Brain,
} from "lucide-react"
import { companiesApi, companiesAdminApi, companyMembersApi } from "@/modules/companies/services/api"
import type { Company, CompanyMember, CompanyClassifyResult } from "@/modules/companies/types"

export default function AdminCompanyDetailPage() {
  const router = useRouter()
  const params = useParams()
  const locale = useLocale()
  const t = useTranslations("admin.companies")
  const companyId = params.id as string

  const [company, setCompany] = useState<Company | null>(null)
  const [members, setMembers] = useState<CompanyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [membersLoading, setMembersLoading] = useState(false)
  const [classifying, setClassifying] = useState(false)
  const [classifyResult, setClassifyResult] = useState<CompanyClassifyResult | null>(null)

  const fetchCompany = useCallback(async () => {
    setLoading(true)
    try {
      const data = await companiesApi.getById(companyId)
      setCompany(data)
    } catch (err) {
      console.error("Failed to fetch company:", err)
    } finally {
      setLoading(false)
    }
  }, [companyId])

  const fetchMembers = useCallback(async () => {
    setMembersLoading(true)
    try {
      const data = await companyMembersApi.getAll(companyId)
      setMembers(data)
    } catch (err) {
      console.error("Failed to fetch members:", err)
    } finally {
      setMembersLoading(false)
    }
  }, [companyId])

  useEffect(() => { fetchCompany() }, [fetchCompany])

  const handleVerify = async () => {
    if (!company) return
    const msg = company.is_verified ? t("unverifyConfirm") : t("verifyConfirm")
    if (!window.confirm(msg)) return
    try {
      await companiesAdminApi.verify(companyId, !company.is_verified)
      fetchCompany()
    } catch (err) {
      console.error("Verify failed:", err)
    }
  }

  const handleClassify = async () => {
    setClassifying(true)
    setClassifyResult(null)
    try {
      const result = await companiesAdminApi.classify(companyId)
      setClassifyResult(result)
      fetchCompany() // refresh to show updated regimen
    } catch (err) {
      console.error("Classify failed:", err)
    } finally {
      setClassifying(false)
    }
  }

  const basePath = `/${locale}/dashboard/admin/companies`

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!company) {
    return (
      <div className="p-4 space-y-4">
        <Button variant="ghost" onClick={() => router.push(basePath)}>
          <ArrowLeft className="h-4 w-4 mr-2" /> {t("noResults")}
        </Button>
      </div>
    )
  }

  const formatDate = (d?: string | null) => d ? new Date(d).toLocaleDateString() : "-"

  const InfoRow = ({ label, value }: { label: React.ReactNode; value: React.ReactNode }) => (
    <div className="flex justify-between py-2 border-b last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right max-w-[60%] truncate">{value || "-"}</span>
    </div>
  )

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(basePath)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <Building2 className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">{company.legal_name}</h1>
            <Badge variant={company.is_active ? "default" : "secondary"}>
              {company.is_active ? t("active") : t("inactive")}
            </Badge>
            {company.is_verified ? (
              <Badge className="bg-green-100 text-green-700 hover:bg-green-100">
                <CheckCircle className="h-3 w-3 mr-1" /> {t("verified")}
              </Badge>
            ) : (
              <Badge variant="outline" className="text-gray-500">
                <XCircle className="h-3 w-3 mr-1" /> {t("unverified")}
              </Badge>
            )}
          </div>
          {company.trade_name && (
            <p className="text-sm text-muted-foreground mt-1">{company.trade_name}</p>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleClassify} disabled={classifying}>
            {classifying ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Brain className="h-4 w-4 mr-1" />}
            {t("classify")}
          </Button>
          <Button variant="outline" size="sm" onClick={handleVerify}>
            <ShieldCheck className="h-4 w-4 mr-1" />
            {company.is_verified ? t("unverify") : t("verify")}
          </Button>
        </div>
      </div>

      {/* Classification result */}
      {classifyResult && (
        <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
          <p className="font-medium text-blue-800">
            {t("classifyResult", {
              regimen: classifyResult.regimen_fiscal,
              confidence: Math.round(classifyResult.confidence * 100),
            })}
          </p>
          <p className="text-blue-600 mt-1">{classifyResult.reason}</p>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="info" onValueChange={(v) => { if (v === "members") fetchMembers() }}>
        <TabsList>
          <TabsTrigger value="info" className="gap-1">
            <FileText className="h-4 w-4" /> Info
          </TabsTrigger>
          <TabsTrigger value="members" className="gap-1">
            <Users className="h-4 w-4" /> {t("members")} ({company.member_count || 0})
          </TabsTrigger>
        </TabsList>

        {/* Info Tab */}
        <TabsContent value="info" className="mt-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Identity */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <Building2 className="h-4 w-4" /> Identidad
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-0">
                <InfoRow label={t("legalName")} value={company.legal_name} />
                <InfoRow label={t("taxId")} value={company.tax_id} />
                {company.nif && <InfoRow label={t("nif")} value={company.nif} />}
                <InfoRow label="Forma Jurídica" value={company.forma_juridica} />
                <InfoRow label="Nacionalidad" value={company.nacionalidad} />
                <InfoRow label="Capital Social" value={company.capital_social != null ? `${Number(company.capital_social).toLocaleString()} XAF` : null} />
                {company.registration_number && <InfoRow label="N° Registro" value={company.registration_number} />}
                <InfoRow label={<span className="flex items-center gap-1"><Calendar className="h-3 w-3" /> Fecha Registro</span>} value={formatDate(company.registration_date)} />
              </CardContent>
            </Card>

            {/* Activity */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Actividad</CardTitle>
              </CardHeader>
              <CardContent className="space-y-0">
                <InfoRow label="Sector" value={company.sector_actividad} />
                <InfoRow label="Subsector" value={company.subsector_actividad} />
                <InfoRow label="Tipo Comercio" value={company.commerce_type} />
                <InfoRow label={t("regimen")} value={
                  company.regimen_fiscal ? (
                    <Badge variant="outline">{t(company.regimen_fiscal)}</Badge>
                  ) : "-"
                } />
                <InfoRow label="Objeto Social" value={company.objeto_social} />
              </CardContent>
            </Card>

            {/* Location & Contact */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <MapPin className="h-4 w-4" /> Ubicación y Contacto
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-0">
                <InfoRow label="Dirección" value={company.address} />
                <InfoRow label={t("city")} value={company.city_name} />
                <InfoRow label={t("zone")} value={company.zone_code} />
                <InfoRow label={<span className="flex items-center gap-1"><Phone className="h-3 w-3" /> Teléfono</span>} value={company.phone} />
                <InfoRow label={<span className="flex items-center gap-1"><Mail className="h-3 w-3" /> Email</span>} value={company.email} />
              </CardContent>
            </Card>

            {/* Operational */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Operacional</CardTitle>
              </CardHeader>
              <CardContent className="space-y-0">
                <InfoRow label="Empleados" value={company.employee_count} />
                <InfoRow label="Establecimientos" value={company.establishment_count} />
                <InfoRow label={t("members")} value={company.member_count || 0} />
                <InfoRow label="Creada" value={formatDate(company.created_at)} />
                <InfoRow label="Actualizada" value={formatDate(company.updated_at)} />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Members Tab */}
        <TabsContent value="members" className="mt-4">
          <Card>
            <CardContent className="p-0">
              {membersLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : members.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>{t("noResults")}</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Nombre</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead>Rol</TableHead>
                      <TableHead>{t("status")}</TableHead>
                      <TableHead>Asignado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {members.map((m) => (
                      <TableRow key={m.user_id}>
                        <TableCell className="font-medium">{m.user_name || "-"}</TableCell>
                        <TableCell className="text-sm">{m.user_email || "-"}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">{m.role}</Badge>
                        </TableCell>
                        <TableCell>
                          {m.is_active ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <XCircle className="h-4 w-4 text-gray-400" />
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(m.assigned_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
