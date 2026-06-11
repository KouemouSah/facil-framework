/**
 * OMS Shared Formatters & Constants
 *
 * Centralizes formatting and status config used across all OMS pages.
 */

import { Clock, Play, CheckCircle2, DollarSign, AlertTriangle, XCircle } from 'lucide-react'

// =============================================================================
// Number formatting
// =============================================================================

export function fmtXAF(n: number | null | undefined, locale = 'es-GQ'): string {
  if (n == null || isNaN(n)) return '0 XAF'
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n) + ' XAF'
}

export function fmtK(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

// =============================================================================
// Date formatting
// =============================================================================

export function fmtDate(dateStr: string | null | undefined, locale = 'es-GQ'): string {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit', month: 'short', year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

// =============================================================================
// Status config
// =============================================================================

export const OBLIGATION_STATUS_CONFIG: Record<string, {
  color: string; label: string; labelKey: string; icon: typeof Clock
}> = {
  pending:    { color: 'bg-yellow-100 text-yellow-800', label: 'Pendiente',  labelKey: 'status.pending',    icon: Clock },
  processing: { color: 'bg-blue-100 text-blue-800',    label: 'En proceso', labelKey: 'status.processing', icon: Play },
  completed:  { color: 'bg-green-100 text-green-800',  label: 'Completado', labelKey: 'status.completed',  icon: CheckCircle2 },
  paid:       { color: 'bg-emerald-100 text-emerald-800', label: 'Pagado',  labelKey: 'status.paid',       icon: DollarSign },
  overdue:    { color: 'bg-red-100 text-red-800',      label: 'Vencido',    labelKey: 'status.overdue',    icon: AlertTriangle },
  cancelled:  { color: 'bg-gray-100 text-gray-800',    label: 'Cancelado',  labelKey: 'status.cancelled',  icon: XCircle },
}

export const LICENSE_STATUS_CONFIG: Record<string, {
  color: string; label: string; icon: typeof Clock
}> = {
  open:      { color: 'bg-blue-100 text-blue-800',    label: 'Abierta',    icon: Play },
  partial:   { color: 'bg-yellow-100 text-yellow-800', label: 'Parcial',   icon: Clock },
  overdue:   { color: 'bg-red-100 text-red-800',      label: 'Vencida',    icon: AlertTriangle },
  complete:  { color: 'bg-green-100 text-green-800',  label: 'Completa',   icon: CheckCircle2 },
  cancelled: { color: 'bg-gray-100 text-gray-800',    label: 'Cancelada',  icon: XCircle },
}
