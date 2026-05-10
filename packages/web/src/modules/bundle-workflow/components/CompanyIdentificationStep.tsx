'use client'

import { useState } from 'react'
import { Search, Building2, Plus, Loader2 } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { MyCompanyCard } from './MyCompanyCard'
import { CompanyInfoCard } from './CompanyInfoCard'
import type { UseBundleWizardReturn } from '../hooks/useBundleWizard'

interface CompanyIdentificationStepProps {
  wizard: UseBundleWizardReturn
  locale: string
}

const labels = {
  title: {
    es: 'Identificacion de la Empresa',
    fr: "Identification de l'Entreprise",
    en: 'Company Identification',
  },
  subtitle: {
    es: 'Busque su empresa o seleccione una de la lista.',
    fr: 'Recherchez votre entreprise ou selectionnez-en une dans la liste.',
    en: 'Search for your company or select one from the list.',
  },
  searchPlaceholder: {
    es: 'Buscar por NIF, PE-XXXX o nombre...',
    fr: 'Rechercher par NIF, PE-XXXX ou nom...',
    en: 'Search by NIF, PE-XXXX or name...',
  },
  myCompanies: {
    es: 'Mis empresas',
    fr: 'Mes entreprises',
    en: 'My companies',
  },
  searchResults: {
    es: 'Resultados de busqueda',
    fr: 'Resultats de recherche',
    en: 'Search results',
  },
  noResults: {
    es: 'No se encontro ninguna empresa. ¿Es nueva?',
    fr: "Aucune entreprise trouvee. C'est une nouvelle ?",
    en: 'No company found. Is it a new one?',
  },
  newCompany: {
    es: 'Registrar nueva empresa',
    fr: 'Enregistrer nouvelle entreprise',
    en: 'Register new company',
  },
  newCompanyDesc: {
    es: 'Suba el certificado del Padron Empresarial para registrar automaticamente su empresa.',
    fr: "Chargez le certificat du Registre des Entreprises pour enregistrer automatiquement votre entreprise.",
    en: 'Upload the Business Registry certificate to automatically register your company.',
  },
  thirdParty: {
    es: 'Esta empresa fue registrada por otro usuario. Puede continuar como representante.',
    fr: "Cette entreprise a ete enregistree par un autre utilisateur. Vous pouvez continuer en tant que representant.",
    en: 'This company was registered by another user. You can continue as a representative.',
  },
  select: {
    es: 'Seleccionar',
    fr: 'Selectionner',
    en: 'Select',
  },
  noCompanies: {
    es: 'No tiene empresas registradas. Busque o registre una nueva.',
    fr: "Vous n'avez pas d'entreprises enregistrees. Recherchez ou enregistrez-en une nouvelle.",
    en: 'You have no registered companies. Search or register a new one.',
  },
} as const

export function CompanyIdentificationStep({ wizard, locale }: CompanyIdentificationStepProps) {
  const lang = (locale === 'fr' ? 'fr' : locale === 'en' ? 'en' : 'es') as 'es' | 'fr' | 'en'
  const [searchQuery, setSearchQuery] = useState('')

  const hasSearchQuery = searchQuery.length >= 2
  const showMyCompanies = !hasSearchQuery && wizard.myCompanies.length > 0
  const showSearchResults = hasSearchQuery
  const showNoResults = hasSearchQuery && !wizard.isSearching && wizard.searchResults.length === 0

  const handleSearchChange = (value: string) => {
    setSearchQuery(value)
    wizard.searchCompany(value)
  }

  // If company already selected, show summary
  if (wizard.selectedCompany) {
    return (
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        </div>
        <CompanyInfoCard
          company={wizard.selectedCompany}
          locale={locale}
          onClear={wizard.clearCompanySelection}
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">{labels.title[lang]}</h2>
        <p className="text-sm text-muted-foreground mt-1">{labels.subtitle[lang]}</p>
      </div>

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          value={searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          placeholder={labels.searchPlaceholder[lang]}
          className="pl-10"
        />
        {wizard.isSearching && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* My Companies section */}
      {showMyCompanies && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground border-b pb-2">
            {labels.myCompanies[lang]}
          </h3>
          <div className="space-y-2">
            {wizard.isLoadingCompanies ? (
              <>
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </>
            ) : (
              wizard.myCompanies.map((item) => (
                <MyCompanyCard
                  key={item.company.id}
                  data={item}
                  locale={locale}
                  onSelect={wizard.selectCompany}
                />
              ))
            )}
          </div>
          {/* Always show "Register new" below existing companies */}
          {!wizard.isLoadingCompanies && (
            <div className="border-t pt-3 mt-3">
              <Button variant="outline" onClick={wizard.requestNewCompany} className="gap-2 w-full">
                <Plus className="h-4 w-4" />
                {labels.newCompany[lang]}
              </Button>
              <p className="text-xs text-muted-foreground text-center mt-1.5">
                {labels.newCompanyDesc[lang]}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Search results */}
      {showSearchResults && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-muted-foreground border-b pb-2">
            {labels.searchResults[lang]} ({wizard.searchResults.length})
          </h3>
          {wizard.isSearching ? (
            <div className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : (
            <div className="space-y-2">
              {wizard.searchResults.map((result) => (
                <div
                  key={result.id}
                  className="flex items-center justify-between p-3 rounded-lg border hover:bg-accent/50 cursor-pointer transition-colors"
                  onClick={() => wizard.selectCompany(result)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Building2 className="h-5 w-5 text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{result.legalName}</p>
                      <p className="text-xs text-muted-foreground">
                        {result.registrationNumber || result.taxId}
                        {result.cityName && ` · ${result.cityName}`}
                        {result.zoneCode && ` (${result.zoneCode})`}
                      </p>
                      {!result.registeredByCurrentUser && (
                        <p className="text-xs text-amber-600 mt-0.5">
                          {labels.thirdParty[lang]}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {result.isVerified && (
                      <Badge variant="outline" className="text-xs">✓</Badge>
                    )}
                    <Button size="sm" variant="outline">
                      {labels.select[lang]} →
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* No results → register new */}
      {showNoResults && (
        <div className="text-center py-8 space-y-4">
          <p className="text-sm text-muted-foreground">{labels.noResults[lang]}</p>
          <Button variant="outline" onClick={wizard.requestNewCompany} className="gap-2">
            <Plus className="h-4 w-4" />
            {labels.newCompany[lang]}
          </Button>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            {labels.newCompanyDesc[lang]}
          </p>
        </div>
      )}

      {/* No companies at all */}
      {!hasSearchQuery && !wizard.isLoadingCompanies && wizard.myCompanies.length === 0 && (
        <div className="text-center py-6 space-y-3">
          <p className="text-sm text-muted-foreground">{labels.noCompanies[lang]}</p>
          <Button variant="outline" onClick={wizard.requestNewCompany} className="gap-2">
            <Plus className="h-4 w-4" />
            {labels.newCompany[lang]}
          </Button>
        </div>
      )}
    </div>
  )
}
