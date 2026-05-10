/**
 * Supervisor Company Detail — Re-exports admin company detail page.
 *
 * Supervisors access company details via /supervisor/companies/[id]
 * instead of /admin/companies/[id]. Backend permissions (company.view)
 * are checked per-request — no security bypass.
 */
export { default } from '@/app/[locale]/(dashboard)/dashboard/admin/companies/[id]/page'
