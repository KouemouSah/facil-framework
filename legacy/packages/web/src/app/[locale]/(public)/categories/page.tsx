'use client'

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  ArrowRight, Building, AlertCircle, Loader2, LayoutGrid, List,
  ChevronLeft, ChevronRight
} from "lucide-react"
import { useRouter, useParams } from "next/navigation"
import { useEffect, useState } from "react"
import { useTranslations } from 'next-intl'
import { getCategoryDirectory, getDefaultCategoryDirectory, type CategoryDirectory, type CategoryWithServices } from "@/core/api/homepage"
import Breadcrumb from "@/components/ui/breadcrumb"
import { getLocalizedName, getLocalizedDescription } from '@/core/utils/i18n-helpers'

type ViewMode = 'kanban' | 'list'

const ITEMS_PER_PAGE = 12

/**
 * Page des catégories - Affiche toutes les catégories avec vues multiples
 * Localized version with i18n support
 */
export default function CategoriesPage() {
  const router = useRouter()
  const params = useParams()
  const locale = (params?.locale as string) || 'es'
  const t = useTranslations('categories')
  const tCommon = useTranslations('common')

  const [directory, setDirectory] = useState<CategoryDirectory | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // View and pagination state
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [currentPage, setCurrentPage] = useState(1)

  useEffect(() => {
    async function fetchDirectory() {
      try {
        setLoading(true)
        setError(null)
        const data = await getCategoryDirectory(locale)
        setDirectory(data)
      } catch (err) {
        console.error('Failed to fetch category directory:', err)
        const errorMessage = err instanceof Error ? err.message : 'Failed to load category directory'
        setError(errorMessage)
        setDirectory(getDefaultCategoryDirectory())
      } finally {
        setLoading(false)
      }
    }

    fetchDirectory()
  }, [locale])

  // Pagination logic
  const allCategories = directory?.categories || []
  const totalPages = Math.ceil(allCategories.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const currentCategories = allCategories.slice(startIndex, endIndex)

  const handlePreviousPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleCategoryClick = (category: CategoryWithServices) => {
    router.push(`/${locale}/services?category=${category.category_code}`)
  }

  // Get localized category name/description based on locale
  const getCategoryName = (category: CategoryWithServices) =>
    getLocalizedName(category as unknown as Record<string, unknown>, locale)

  const getCategoryDescription = (category: CategoryWithServices) =>
    getLocalizedDescription(category as unknown as Record<string, unknown>, locale)

  return (
    <div className="container mx-auto px-4 py-8 bg-background">
          {/* Breadcrumbs */}
          <Breadcrumb
            items={[
              { label: t('title') }
            ]}
            className="mb-6"
          />

          {/* Header with view toggle */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
            <div>
              <h1 className="text-4xl font-bold mb-2">{t('allCategories')}</h1>
              <p className="text-muted-foreground text-lg">
                {loading
                  ? t('loading')
                  : t('summary', {
                      categoryCount: directory?.total_categories || 0,
                      serviceCount: directory?.total_services || 0
                    })
                }
              </p>
            </div>

            {/* View Mode Toggle */}
            {!loading && currentCategories.length > 0 && (
              <div className="flex items-center gap-2 bg-muted p-1 rounded-lg">
                <Button
                  variant={viewMode === 'kanban' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('kanban')}
                  className="gap-2"
                >
                  <LayoutGrid className="h-4 w-4" />
                  <span className="hidden sm:inline">{tCommon('viewKanban')}</span>
                </Button>
                <Button
                  variant={viewMode === 'list' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setViewMode('list')}
                  className="gap-2"
                >
                  <List className="h-4 w-4" />
                  <span className="hidden sm:inline">{tCommon('viewList')}</span>
                </Button>
              </div>
            )}
          </div>

          {/* Error Alert */}
          {error && !loading && (
            <Alert variant="destructive" className="mb-6">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                {t('errorLoading')}: {error}
              </AlertDescription>
            </Alert>
          )}

          {/* Loading State */}
          {loading && (
            <div className="flex justify-center items-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-3 text-muted-foreground">{t('loading')}</span>
            </div>
          )}

          {/* Empty State */}
          {!loading && currentCategories.length === 0 && (
            <Card className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">{t('noCategories')}</h3>
              <p className="text-muted-foreground">
                {t('directoryNotAvailable')}
              </p>
            </Card>
          )}

          {/* Kanban View */}
          {!loading && currentCategories.length > 0 && viewMode === 'kanban' && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-4 gap-6">
              {currentCategories.map((category) => (
                <Card
                  key={category.id}
                  className="group cursor-pointer hover:shadow-lg transition-all duration-300"
                  onClick={() => handleCategoryClick(category)}
                >
                  <div className="p-6 space-y-4">
                    {/* Category Header */}
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          {category.icon && (
                            <span className="text-xl">{category.icon}</span>
                          )}
                        </div>
                        <h3 className="font-semibold text-base mb-1 group-hover:text-primary transition-colors line-clamp-2">
                          {getCategoryName(category)}
                        </h3>
                      </div>
                    </div>

                    {/* Description */}
                    {getCategoryDescription(category) && (
                      <p className="text-sm text-muted-foreground line-clamp-3">
                        {getCategoryDescription(category)}
                      </p>
                    )}

                    {/* Footer */}
                    <div className="pt-4 border-t space-y-2">
                      {/* Service Count */}
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-semibold text-primary">
                          {t('serviceCount', { count: category.service_count })}
                        </span>
                        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:translate-x-1 transition-transform" />
                      </div>

                      {/* Ministry/Sector Info */}
                      {(category.ministry_name || category.sector_name) && (
                        <div className="flex items-center text-xs text-muted-foreground">
                          <Building className="mr-1 h-3 w-3 flex-shrink-0" />
                          <span className="truncate">
                            {category.ministry_name || category.sector_name}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* List View */}
          {!loading && currentCategories.length > 0 && viewMode === 'list' && (
            <div className="space-y-4">
              {currentCategories.map((category) => (
                <Card
                  key={category.id}
                  className="group cursor-pointer hover:shadow-md transition-all duration-300"
                  onClick={() => handleCategoryClick(category)}
                >
                  <div className="p-6 flex items-center gap-6">
                    {/* Icon */}
                    {category.icon && (
                      <div className="flex-shrink-0">
                        <span className="text-3xl">{category.icon}</span>
                      </div>
                    )}

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-lg mb-1 group-hover:text-primary transition-colors">
                        {getCategoryName(category)}
                      </h3>
                      {getCategoryDescription(category) && (
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                          {getCategoryDescription(category)}
                        </p>
                      )}
                      {(category.ministry_name || category.sector_name) && (
                        <div className="flex items-center text-xs text-muted-foreground">
                          <Building className="mr-1 h-3 w-3 flex-shrink-0" />
                          <span className="truncate">
                            {category.ministry_name || category.sector_name}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Service Count */}
                    <div className="flex-shrink-0 flex items-center gap-4">
                      <div className="text-right">
                        <div className="text-2xl font-bold text-primary">
                          {category.service_count}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {category.service_count === 1 ? t('service') : t('services')}
                        </div>
                      </div>
                      <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* Pagination */}
          {!loading && totalPages > 1 && (
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
              <Button
                variant="outline"
                onClick={handlePreviousPage}
                disabled={currentPage === 1}
                className="gap-2 w-full sm:w-auto"
              >
                <ChevronLeft className="h-4 w-4" />
                {tCommon('previous')}
              </Button>

              <div className="flex flex-col sm:flex-row items-center gap-2 text-center">
                <span className="text-sm text-muted-foreground">
                  {tCommon('pageOf', { current: currentPage, total: totalPages })}
                </span>
                <span className="text-xs text-muted-foreground">
                  ({startIndex + 1}-{Math.min(endIndex, allCategories.length)} {tCommon('of')} {allCategories.length})
                </span>
              </div>

              <Button
                variant="outline"
                onClick={handleNextPage}
                disabled={currentPage === totalPages}
                className="gap-2 w-full sm:w-auto"
              >
                {tCommon('next')}
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
  )
}
