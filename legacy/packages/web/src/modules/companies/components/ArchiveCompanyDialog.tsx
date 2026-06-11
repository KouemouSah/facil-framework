/**
 * Archive Company Dialog (citizen surface).
 *
 * Confirmation modal for the citizen-driven soft-delete (archive) flow.
 * Owner-only — the parent must already have gated visibility on
 * `useCompanyMembership(companyId, userId).canArchive`.
 *
 * Two states:
 *   1. Idle / submitting — prompts the user with the archive consequences.
 *   2. Blocked (after a 409 response) — lists the dependency counts that
 *      prevent the archive (active licences, pending payments, open requests,
 *      active inspections) and offers a deep-link to the obligations tab.
 *
 * Backend reference: POST /api/v1/companies/{id}/archive — see
 * .claude/plans/SOFT_DELETE_COMPANIES_PLAN.md (Phase 1.4).
 */

'use client'

import * as React from 'react'
import {
  AlertTriangle,
  ArchiveIcon,
  Loader2,
  ShieldAlert,
} from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

import {
  getArchiveBlockers,
  isArchiveBlockedError,
  useArchiveCompany,
  type ArchiveBlockers,
} from '../hooks/useCompanyArchive'

interface Props {
  companyId: string
  companyName: string
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Called after a successful archive. Parent typically navigates back. */
  onSuccess?: () => void
  /** Optional deep-link target shown in the blockers fallback. */
  blockersTabHref?: string
}

function formatBlockers(blockers: ArchiveBlockers): Array<{
  key: keyof ArchiveBlockers
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

export function ArchiveCompanyDialog({
  companyId,
  companyName,
  open,
  onOpenChange,
  onSuccess,
  blockersTabHref,
}: Props) {
  const archive = useArchiveCompany()

  const blockers = React.useMemo<ArchiveBlockers | null>(
    () => getArchiveBlockers(archive.error),
    [archive.error],
  )
  const blocked = !!blockers && blockers && Object.values(blockers).some((c) => c > 0)
  const blockerEntries = blockers ? formatBlockers(blockers) : []

  const handleConfirm = () => {
    archive.mutate(companyId, {
      onSuccess: () => {
        archive.reset()
        onOpenChange(false)
        onSuccess?.()
      },
      // onError handled via the `archive.error` selector below — no toast here
      // because the dialog renders the structured 409 itself.
    })
  }

  // Reset dialog state when the modal is dismissed.
  React.useEffect(() => {
    if (!open) archive.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {blocked ? (
              <>
                <ShieldAlert className="h-5 w-5 text-orange-500" />
                No se puede archivar
              </>
            ) : (
              <>
                <ArchiveIcon className="h-5 w-5" />
                Archivar empresa
              </>
            )}
          </DialogTitle>
          <DialogDescription className="pt-1">
            {blocked
              ? `«${companyName}» tiene actividades en curso que deben resolverse antes de archivar.`
              : `«${companyName}» dejará de aparecer en tu lista de empresas y no podrás iniciar nuevos trámites para ella.`}
          </DialogDescription>
        </DialogHeader>

        {blocked ? (
          <Alert variant="default" className="border-orange-200 bg-orange-50">
            <AlertTriangle className="h-4 w-4 text-orange-600" />
            <AlertTitle>Actividades en curso</AlertTitle>
            <AlertDescription>
              <ul className="mt-2 ml-4 list-disc space-y-0.5 text-sm">
                {blockerEntries.map(({ key, count, label }) => (
                  <li key={key}>
                    <strong>{count}</strong> {label}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">
                Resuelve estas actividades (paga, cancela o completa) antes de
                volver a intentar archivar la empresa.
              </p>
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-3 text-sm">
            <p>
              <strong>Esto NO es una eliminación.</strong> Los registros
              históricos (licencias, pagos, recibos, inspecciones) quedan
              conservados conforme a la ley fiscal.
            </p>
            <ul className="ml-4 list-disc space-y-0.5 text-muted-foreground">
              <li>Un administrador puede restaurar la empresa en cualquier momento.</li>
              <li>Los miembros de la empresa pierden el acceso.</li>
              <li>Se conserva el historial para auditoría.</li>
            </ul>
          </div>
        )}

        {archive.isError && !isArchiveBlockedError(archive.error) ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {archive.error instanceof Error
                ? archive.error.message
                : 'Error desconocido al archivar la empresa.'}
            </AlertDescription>
          </Alert>
        ) : null}

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={archive.isPending}
          >
            {blocked ? 'Cerrar' : 'Cancelar'}
          </Button>
          {blocked && blockersTabHref ? (
            <Button asChild variant="default">
              <a href={blockersTabHref}>Ver mis obligaciones</a>
            </Button>
          ) : !blocked ? (
            <Button
              variant="default"
              onClick={handleConfirm}
              disabled={archive.isPending}
            >
              {archive.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Archivando…
                </>
              ) : (
                <>
                  <ArchiveIcon className="mr-2 h-4 w-4" />
                  Sí, archivar
                </>
              )}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
