'use client'

/**
 * Admin — Archived Companies (Phase 4 of SOFT_DELETE_COMPANIES_PLAN).
 *
 * Lists soft-deleted companies (`archived_at IS NOT NULL`) and exposes the
 * two admin recovery actions:
 *   - Restaurar     -> POST /companies/{id}/unarchive (perm: company.unarchive)
 *   - Eliminar      -> DELETE /companies/{id}        (perm: company.hard_delete,
 *                                                      requires archived_at)
 *
 * Both actions re-check blockers server-side (active_licenses,
 * pending_payments, open_requests, active_inspections) — the page surfaces
 * the same structured 409 payload as the citizen archive flow does.
 *
 * @route /[locale]/dashboard/admin/companies/archived
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Archive,
  ArrowLeft,
  Building2,
  RefreshCw,
  RotateCcw,
  Search,
  Trash2,
} from 'lucide-react'
import Link from 'next/link'
import { useParams } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Loader2, AlertTriangle } from 'lucide-react'

import { companiesAdminApi } from '@/modules/companies/services/api'
import type { Company } from '@/modules/companies/types'
import {
  getArchiveBlockers,
  isArchiveBlockedError,
  useHardDeleteCompany,
  useUnarchiveCompany,
  type ArchiveBlockers,
} from '@/modules/companies/hooks/useCompanyArchive'

const REASON_LABEL: Record<string, string> = {
  archived_by_owner: 'Archivada por el propietario',
  archived_by_admin: 'Archivada por administrador',
  merged: 'Fusionada',
  inactive_long_term: 'Inactiva (auto)',
}

function fmtDate(d: string | null | undefined): string {
  if (!d) return '—'
  try {
    return new Date(d).toLocaleString('es-GQ', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return d
  }
}

function formatBlockers(blockers: ArchiveBlockers): Array<{
  key: string
  count: number
  label: string
}> {
  const labels: Record<keyof ArchiveBlockers, string> = {
    active_licenses: 'licencia(s) activa(s)',
    pending_payments: 'pago(s) en proceso',
    open_requests: 'solicitud(es) abierta(s)',
    active_inspections: 'inspección(es) en curso',
  }
  return (Object.entries(blockers) as Array<[keyof ArchiveBlockers, number]>)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => ({ key, count, label: labels[key] }))
}

export default function ArchivedCompaniesPage() {
  const params = useParams()
  const locale = (params.locale as string) ?? 'es'

  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Debounce search to avoid hammering the API on every keystroke.
  useMemo(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(handle)
  }, [search])

  const list = useQuery({
    queryKey: ['admin-companies-archived', page, debouncedSearch],
    queryFn: () =>
      companiesAdminApi.listAll({
        page,
        pageSize: 20,
        archived: 'archived',
        search: debouncedSearch || undefined,
        sortBy: 'created_at',
        sortOrder: 'desc',
      }),
    staleTime: 30_000,
  })

  const items = list.data?.items ?? []
  const total = list.data?.total ?? 0
  const totalPages = list.data ? Math.ceil(total / list.data.page_size) : 0

  // Action dialog state — single dialog reused for both restore + hard-delete.
  type ActionMode = 'restore' | 'hardDelete'
  const [dialogState, setDialogState] = useState<{
    company: Company
    mode: ActionMode
  } | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')

  const unarchive = useUnarchiveCompany()
  const hardDelete = useHardDeleteCompany()

  const activeMutation = dialogState?.mode === 'restore' ? unarchive : hardDelete
  const blockers = useMemo<ArchiveBlockers | null>(
    () => getArchiveBlockers(activeMutation.error),
    [activeMutation.error],
  )
  const isBlocked = !!blockers && Object.values(blockers).some((c) => c > 0)
  const isUnknownError =
    activeMutation.isError && !isArchiveBlockedError(activeMutation.error)

  const closeDialog = () => {
    setDialogState(null)
    setDeleteConfirm('')
    unarchive.reset()
    hardDelete.reset()
  }

  const handleConfirm = () => {
    if (!dialogState) return
    activeMutation.mutate(dialogState.company.id, {
      onSuccess: () => {
        closeDialog()
        list.refetch()
      },
    })
  }

  const hardDeleteReady =
    dialogState?.mode === 'hardDelete'
      ? deleteConfirm.trim().toUpperCase() === 'ELIMINAR'
      : true

  return (
    <div className="space-y-5 p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="icon">
          <Link href={`/${locale}/dashboard/admin/companies`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Archive className="h-5 w-5" />
            Empresas archivadas
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Lista de empresas con soft-delete. Las acciones de restauración y
            eliminación definitiva re-validan las dependencias activas en el
            backend (licencias, pagos, solicitudes, inspecciones).
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => list.refetch()}
          disabled={list.isFetching}
        >
          <RefreshCw
            className={`h-3.5 w-3.5 mr-1 ${list.isFetching ? 'animate-spin' : ''}`}
          />
          Refrescar
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Buscar por nombre, NIF o número de registro…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="pl-9"
            />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            {list.isLoading
              ? 'Cargando…'
              : `${total} empresa(s) archivada(s)`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {list.isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              No hay empresas archivadas.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Empresa</TableHead>
                  <TableHead>NIF / Reg.</TableHead>
                  <TableHead>Archivada</TableHead>
                  <TableHead>Por</TableHead>
                  <TableHead>Razón</TableHead>
                  <TableHead className="text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="font-medium">{c.legal_name}</span>
                      </div>
                      {c.commerce_type && (
                        <Badge variant="secondary" className="mt-1 text-[10px] h-4">
                          {c.commerce_type}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {c.nif ?? '—'}
                      <br />
                      <span className="text-muted-foreground">
                        {c.registration_number ?? '—'}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">
                      {fmtDate(c.archived_at)}
                    </TableCell>
                    <TableCell className="text-xs">
                      {c.archived_by_name ?? c.archived_by_email ?? '—'}
                    </TableCell>
                    <TableCell className="text-xs">
                      {c.archive_reason
                        ? REASON_LABEL[c.archive_reason] ?? c.archive_reason
                        : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs gap-1"
                          onClick={() =>
                            setDialogState({ company: c, mode: 'restore' })
                          }
                        >
                          <RotateCcw className="h-3 w-3" /> Restaurar
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs gap-1 text-red-700 border-red-200 hover:bg-red-50"
                          onClick={() =>
                            setDialogState({ company: c, mode: 'hardDelete' })
                          }
                        >
                          <Trash2 className="h-3 w-3" /> Eliminar
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 text-xs">
              <span className="text-muted-foreground">
                Página {page} / {totalPages}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Siguiente
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Action dialog (restore + hard-delete share the same modal) */}
      <Dialog
        open={!!dialogState}
        onOpenChange={(open) => !open && closeDialog()}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {dialogState?.mode === 'restore' ? (
                <>
                  <RotateCcw className="h-5 w-5 text-emerald-600" />
                  Restaurar empresa
                </>
              ) : (
                <>
                  <Trash2 className="h-5 w-5 text-red-600" />
                  Eliminar definitivamente
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {dialogState?.mode === 'restore'
                ? `«${dialogState.company.legal_name}» volverá a aparecer en la lista del propietario y los miembros recuperarán el acceso. Esta acción queda registrada en el audit log.`
                : `«${dialogState?.company.legal_name}» será eliminada definitivamente. Esto borra los user_company_roles asociados pero conserva los registros históricos (commercial_licenses, service_payments, audit_logs) que apuntan a la empresa por ID. Acción IRREVERSIBLE.`}
            </DialogDescription>
          </DialogHeader>

          {/* 409 blockers fallback */}
          {isBlocked && blockers ? (
            <Alert variant="default" className="border-orange-200 bg-orange-50">
              <AlertTriangle className="h-4 w-4 text-orange-600" />
              <AlertTitle>Actividades en curso</AlertTitle>
              <AlertDescription>
                <p className="text-sm">
                  No se puede{' '}
                  {dialogState?.mode === 'restore'
                    ? 'restaurar'
                    : 'eliminar'}{' '}
                  porque la empresa archivada acumuló nuevas dependencias
                  activas:
                </p>
                <ul className="mt-2 ml-4 list-disc space-y-0.5 text-sm">
                  {formatBlockers(blockers).map((b) => (
                    <li key={b.key}>
                      <strong>{b.count}</strong> {b.label}
                    </li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          ) : null}

          {isUnknownError ? (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {activeMutation.error instanceof Error
                  ? activeMutation.error.message
                  : 'Error desconocido.'}
              </AlertDescription>
            </Alert>
          ) : null}

          {/* Hard-delete double confirmation */}
          {dialogState?.mode === 'hardDelete' && !isBlocked ? (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Para confirmar, escribe{' '}
                <code className="font-mono text-xs bg-muted px-1 rounded">
                  ELIMINAR
                </code>
                :
              </p>
              <Input
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder="ELIMINAR"
                autoFocus
              />
            </div>
          ) : null}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={closeDialog}
              disabled={activeMutation.isPending}
            >
              {isBlocked ? 'Cerrar' : 'Cancelar'}
            </Button>
            {!isBlocked && (
              <Button
                variant={
                  dialogState?.mode === 'hardDelete' ? 'destructive' : 'default'
                }
                onClick={handleConfirm}
                disabled={
                  activeMutation.isPending
                  || (dialogState?.mode === 'hardDelete' && !hardDeleteReady)
                }
              >
                {activeMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {dialogState?.mode === 'restore'
                      ? 'Restaurando…'
                      : 'Eliminando…'}
                  </>
                ) : dialogState?.mode === 'restore' ? (
                  'Sí, restaurar'
                ) : (
                  'Eliminar definitivamente'
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
