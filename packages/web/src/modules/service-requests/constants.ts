/**
 * Service Requests - Shared Constants
 *
 * STATUS_BADGE_COLORS: Tailwind background classes for status badges.
 * Used by both the dashboard and service-requests list page.
 */

export const STATUS_BADGE_COLORS: Record<string, string> = {
  DRAFT: 'bg-slate-500',
  TIMBRES_PENDING: 'bg-amber-500',
  TIMBRES_PAID: 'bg-amber-600',
  SUBMITTED: 'bg-blue-500',
  DOCUMENTS_REQUIRED: 'bg-orange-500',
  UNDER_REVIEW: 'bg-indigo-500',
  DOSSIER_VALIDE: 'bg-teal-500',
  REJECTED: 'bg-red-500',
  PENDING_NOTA_INGRESO: 'bg-purple-500',
  NOTA_UPLOADED: 'bg-purple-600',
  PAYMENT_PENDING: 'bg-yellow-500',
  PAYMENT_PROCESSING: 'bg-yellow-600',
  PAID: 'bg-green-500',
  PAYMENT_FAILED: 'bg-red-600',
  CITA_SCHEDULED: 'bg-cyan-500',
  IN_PROGRESS: 'bg-blue-600',
  COMPLETED: 'bg-green-600',
  CANCELLED: 'bg-gray-500',
  EXPIRED: 'bg-gray-600',
}

export const PAYMENT_STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-500',
  pending: 'bg-yellow-500',
  processing: 'bg-blue-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-500',
}
