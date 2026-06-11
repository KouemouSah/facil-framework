'use client'

/**
 * Shared Print Header — consistent across all printable pages
 *
 * Matches the public licencias-comerciales print layout.
 * Hidden on screen, visible only on print (@media print).
 *
 * Usage:
 *   <PrintHeader title="Ficha Empresa" subtitle="ONRC" meta={[{label: 'NIF', value: 'GE123'}]} />
 */

interface PrintHeaderProps {
  title: string
  subtitle: string
  meta?: { label: string; value: string }[]
}

export function PrintHeader({ title, subtitle, meta }: PrintHeaderProps) {
  const printDate = new Date().toLocaleDateString('es-GQ', {
    year: 'numeric', month: 'long', day: 'numeric',
  })

  return (
    <div className="hidden print:block mb-3">
      <div className="flex items-center justify-between border-b-2 border-gray-800 pb-2 mb-2">
        <img src="/logo.png" alt="FACIL" width={80} height={28} className="h-7 w-auto" />
        <div className="text-right">
          <h1 className="text-[11pt] font-bold tracking-wide uppercase">{title}</h1>
          <p className="text-[7pt] text-gray-600">{subtitle} — República de Guinea Ecuatorial</p>
        </div>
      </div>
      <div className="flex justify-between text-[7pt] text-gray-700">
        {meta?.map(m => (
          <span key={m.label}><strong>{m.label}:</strong> {m.value}</span>
        ))}
        <span>{printDate}</span>
      </div>
    </div>
  )
}

/**
 * Print footer — generation date + platform credit
 */
export function PrintFooter() {
  return (
    <div className="hidden print:block mt-4 pt-2 border-t border-gray-300 text-center">
      <p className="text-[8pt] text-gray-400">
        Documento generado el {new Date().toLocaleDateString('es-GQ')} — Plataforma Facil
      </p>
    </div>
  )
}
