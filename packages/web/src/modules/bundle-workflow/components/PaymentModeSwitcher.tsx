'use client'

import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Label } from '@/components/ui/label'
import type { ProcessingMode } from '@/types/service-bundle'

interface PaymentModeSwitcherProps {
  value: ProcessingMode
  onChange: (mode: ProcessingMode) => void
  locale: string
  disabled?: boolean
}

const modeLabels: Record<ProcessingMode, { es: string; fr: string; en: string }> = {
  per_line: {
    es: 'Modo A — Pagar por linea (seleccionar obligaciones)',
    fr: 'Mode A — Payer par ligne (selectionner les obligations)',
    en: 'Mode A — Pay per line (select obligations)',
  },
  consolidated: {
    es: 'Modo B — Pagar todo (pago unico consolidado)',
    fr: 'Mode B — Tout payer (paiement unique consolide)',
    en: 'Mode B — Pay all (single consolidated payment)',
  },
}

const modeDescriptions: Record<ProcessingMode, { es: string; fr: string; en: string }> = {
  per_line: {
    es: 'Seleccione las obligaciones que desea pagar. Cada entidad procesara su parte.',
    fr: 'Selectionnez les obligations a payer. Chaque entite traitera sa partie.',
    en: 'Select the obligations you want to pay. Each entity will process its part.',
  },
  consolidated: {
    es: 'Pague todas las obligaciones pendientes de una vez. Un agente polivalente procesara el dossier.',
    fr: 'Payez toutes les obligations en une seule fois. Un agent polyvalent traitera le dossier.',
    en: 'Pay all pending obligations at once. A polyvalent agent will process the file.',
  },
}

export function PaymentModeSwitcher({ value, onChange, locale, disabled }: PaymentModeSwitcherProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  return (
    <RadioGroup
      value={value}
      onValueChange={(v) => onChange(v as ProcessingMode)}
      disabled={disabled}
      className="space-y-3"
    >
      {(['per_line', 'consolidated'] as ProcessingMode[]).map((mode) => (
        <div
          key={mode}
          className={`flex items-start space-x-3 rounded-lg border p-4 transition-colors ${
            value === mode ? 'border-primary bg-primary/5' : 'border-border'
          }`}
        >
          <RadioGroupItem value={mode} id={`mode-${mode}`} className="mt-0.5" />
          <Label htmlFor={`mode-${mode}`} className="cursor-pointer flex-1">
            <span className="font-medium text-sm">{modeLabels[mode][lang]}</span>
            <p className="text-xs text-muted-foreground mt-1">
              {modeDescriptions[mode][lang]}
            </p>
          </Label>
        </div>
      ))}
    </RadioGroup>
  )
}
