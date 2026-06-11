'use client'

import { Upload, CheckCircle2, Loader2 } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { CompanyInfoCard } from './CompanyInfoCard'
import { BundleErrorAlert } from './BundleErrorAlert'
import type { UseBundleWizardReturn } from '../hooks/useBundleWizard'

interface CompanyUploadStepProps {
  wizard: UseBundleWizardReturn
  locale: string
}

const labels = {
  title: {
    es: 'Registro de Nueva Empresa',
    fr: "Enregistrement d'une Nouvelle Entreprise",
    en: 'New Company Registration',
  },
  subtitle: {
    es: 'Suba el Certificado de Actualizacion del Padron Empresarial para registrar automaticamente su empresa.',
    fr: "Chargez le Certificat de Mise a Jour du Registre des Entreprises pour enregistrer automatiquement votre entreprise.",
    en: 'Upload the Business Registry Update Certificate to automatically register your company.',
  },
  dropzone: {
    es: 'Arrastre su archivo aqui o haga clic para seleccionar',
    fr: 'Glissez votre fichier ici ou cliquez pour selectionner',
    en: 'Drag your file here or click to select',
  },
  formats: {
    es: 'PDF, JPG, PNG (max 10MB)',
    fr: 'PDF, JPG, PNG (max 10 Mo)',
    en: 'PDF, JPG, PNG (max 10MB)',
  },
  extracting: {
    es: 'Extrayendo datos del documento...',
    fr: 'Extraction des donnees du document...',
    en: 'Extracting document data...',
  },
  extracted: {
    es: 'Documento procesado correctamente',
    fr: 'Document traite avec succes',
    en: 'Document processed successfully',
  },
  companyCreated: {
    es: 'Empresa registrada automaticamente',
    fr: 'Entreprise enregistree automatiquement',
    en: 'Company registered automatically',
  },
  verificationPending: {
    es: 'La verificacion por un administrador se realizara en segundo plano. Puede continuar con el pago.',
    fr: "La verification par un administrateur se fera en arriere-plan. Vous pouvez continuer le paiement.",
    en: 'Admin verification will happen in the background. You can continue with payment.',
  },
  retry: {
    es: 'Reintentar',
    fr: 'Reessayer',
    en: 'Retry',
  },
  delete: {
    es: 'Eliminar',
    fr: 'Supprimer',
    en: 'Delete',
  },
} as const

export function CompanyUploadStep({ wizard, locale }: CompanyUploadStepProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    await wizard.uploadDocument(file)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    await wizard.uploadDocument(file)
  }

  // Company already created from extraction
  if (wizard.selectedCompany && wizard.licenseData) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        </div>
        <Alert className="border-green-200 bg-green-50 dark:bg-green-950">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800 dark:text-green-200">
            {labels.companyCreated[lang]}
          </AlertDescription>
        </Alert>
        <CompanyInfoCard company={wizard.selectedCompany} locale={locale} />
        <p className="text-xs text-muted-foreground">{labels.verificationPending[lang]}</p>
      </div>
    )
  }

  // Document uploaded + extraction done
  if (wizard.documentPreview) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        </div>
        <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950">
          <CheckCircle2 className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800 dark:text-blue-200">
            {labels.extracted[lang]}
            {wizard.documentPreview.confidence != null && (
              <span className="ml-2 text-xs opacity-70">
                ({Math.round(wizard.documentPreview.confidence * 100)}%)
              </span>
            )}
          </AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={wizard.deleteDocument}>
            {labels.delete[lang]}
          </Button>
        </div>
      </div>
    )
  }

  // Uploading state
  if (wizard.isUploading) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        </div>
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
          <p className="text-sm text-muted-foreground">{labels.extracting[lang]}</p>
        </div>
      </div>
    )
  }

  // Upload dropzone
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        <p className="text-sm text-muted-foreground mt-1">{labels.subtitle[lang]}</p>
      </div>

      <div
        className="border-2 border-dashed rounded-lg p-12 text-center cursor-pointer hover:border-primary/50 hover:bg-accent/30 transition-colors"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => document.getElementById('bundle-doc-input')?.click()}
      >
        <Upload className="h-10 w-10 text-muted-foreground mx-auto mb-4" />
        <p className="text-sm text-muted-foreground">{labels.dropzone[lang]}</p>
        <p className="text-xs text-muted-foreground mt-2">{labels.formats[lang]}</p>
        <input
          id="bundle-doc-input"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          className="hidden"
          onChange={handleFileSelect}
        />
      </div>

      <BundleErrorAlert
        error={wizard.apiError}
        locale={locale}
        onRetry={() => {
          wizard.clearError()
          if (wizard.documentPreview) wizard.loadClassification()
        }}
        onBack={wizard.goBack}
        onClear={wizard.clearError}
      />
    </div>
  )
}
