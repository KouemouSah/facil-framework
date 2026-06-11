'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  ArrowRight,
  AlertCircle,
  Loader2,
  FileText,
  Award,
  Home,
  ClipboardCheck,
  Search,
  FileSpreadsheet,
  Package,
  Receipt,
  ChevronRight,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import {
  getServicesByType,
  getDefaultServicesByType,
  type ServiceType,
  type ServicesByTypeResponse,
  type ServiceByType,
} from '@/core/api/homepage';
import { getLocalizedName } from '@/core/utils/i18n-helpers';

// Service type configuration with icons and colors
const SERVICE_TYPES: Array<{
  type: ServiceType;
  icon: typeof FileText;
  bgColor: string;
  textColor: string;
}> = [
  { type: 'document_processing', icon: FileText, bgColor: 'bg-blue-100 dark:bg-blue-900/30', textColor: 'text-blue-700 dark:text-blue-300' },
  { type: 'license_permit', icon: Award, bgColor: 'bg-purple-100 dark:bg-purple-900/30', textColor: 'text-purple-700 dark:text-purple-300' },
  { type: 'residence_permit', icon: Home, bgColor: 'bg-green-100 dark:bg-green-900/30', textColor: 'text-green-700 dark:text-green-300' },
  { type: 'registration_fee', icon: ClipboardCheck, bgColor: 'bg-yellow-100 dark:bg-yellow-900/30', textColor: 'text-yellow-700 dark:text-yellow-300' },
  { type: 'inspection_fee', icon: Search, bgColor: 'bg-red-100 dark:bg-red-900/30', textColor: 'text-red-700 dark:text-red-300' },
  { type: 'administrative_tax', icon: FileSpreadsheet, bgColor: 'bg-indigo-100 dark:bg-indigo-900/30', textColor: 'text-indigo-700 dark:text-indigo-300' },
  { type: 'customs_duty', icon: Package, bgColor: 'bg-orange-100 dark:bg-orange-900/30', textColor: 'text-orange-700 dark:text-orange-300' },
  { type: 'declaration_tax', icon: Receipt, bgColor: 'bg-pink-100 dark:bg-pink-900/30', textColor: 'text-pink-700 dark:text-pink-300' },
];

// Number of services to display initially
const DISPLAY_LIMIT = 24;

export const ServicesDirectory = () => {
  const router = useRouter();
  const locale = useLocale();
  const [selectedType, setSelectedType] = useState<ServiceType>('document_processing');
  const [servicesData, setServicesData] = useState<ServicesByTypeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const t = useTranslations('directory');
  const tServiceTypes = useTranslations('serviceTypes');

  // Fetch services when type changes
  useEffect(() => {
    async function fetchServices() {
      try {
        setLoading(true);
        setError(null);
        const data = await getServicesByType(selectedType, {
          language: locale,
          limit: 100, // Load enough for display
        });
        setServicesData(data);
      } catch (err) {
        console.error('Failed to fetch services by type:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to load services';
        setError(errorMessage);
        setServicesData(getDefaultServicesByType(selectedType));
      } finally {
        setLoading(false);
      }
    }

    fetchServices();
  }, [selectedType, locale]);

  const getServiceName = (service: ServiceByType) =>
    getLocalizedName(service as unknown as Record<string, unknown>, locale);

  const handleTypeClick = (type: ServiceType) => {
    setSelectedType(type);
  };

  const handleViewMore = () => {
    router.push(`/${locale}/services?service_type=${selectedType}`);
  };

  const handleServiceClick = (serviceId: number) => {
    router.push(`/${locale}/services/${serviceId}`);
  };

  // Get current type config
  const currentTypeConfig = SERVICE_TYPES.find(t => t.type === selectedType);

  // Services to display (limited)
  const displayedServices = servicesData?.services.slice(0, DISPLAY_LIMIT) || [];
  const hasMore = (servicesData?.services.length || 0) > DISPLAY_LIMIT || servicesData?.has_more;

  return (
    <section className="py-10 bg-background">
      <div className="container mx-auto px-4">
        {/* Header */}
        <div className="mb-6 text-center">
          <h2 className="text-2xl font-bold mb-2">{t('title')}</h2>
          <p className="text-sm text-muted-foreground max-w-xl mx-auto">{t('description')}</p>
        </div>

        {error && !loading && (
          <Alert variant="destructive" className="mb-4 max-w-xl mx-auto">
            <AlertCircle className="h-3 w-3" />
            <AlertDescription className="text-xs">
              {t('errorLoading')}: {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Service Type Pills - Horizontal Scrollable */}
        <div className="mb-6 overflow-x-auto pb-2 -mx-4 px-4">
          <div className="flex gap-2 min-w-max">
            {SERVICE_TYPES.map(({ type, icon: Icon, bgColor, textColor }) => {
              const isSelected = selectedType === type;
              return (
                <button
                  key={type}
                  onClick={() => handleTypeClick(type)}
                  className={`
                    flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium
                    transition-all duration-200 whitespace-nowrap
                    ${isSelected
                      ? 'bg-primary text-primary-foreground shadow-md scale-105'
                      : `${bgColor} ${textColor} hover:scale-102 hover:shadow-sm`
                    }
                  `}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tServiceTypes(`${type}.name`)}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex justify-center items-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="ml-2 text-sm text-muted-foreground">{t('loading')}</span>
          </div>
        )}

        {/* Services Grid */}
        {!loading && servicesData && displayedServices.length > 0 && (
          <>
            {/* Service count badge */}
            <div className="mb-4 flex items-center justify-between">
              <Badge variant="secondary" className="text-xs">
                {servicesData.total} {t('showing', { count: displayedServices.length, total: servicesData.total }).split(' ')[0]}
              </Badge>
              {currentTypeConfig && (
                <span className={`text-xs ${currentTypeConfig.textColor}`}>
                  {tServiceTypes(`${selectedType}.name`)}
                </span>
              )}
            </div>

            {/* Services Grid - 4 columns on desktop, 2 on mobile */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {displayedServices.map((service, index) => (
                <Card
                  key={service.id}
                  onClick={() => handleServiceClick(service.id)}
                  className={`
                    cursor-pointer p-2.5 transition-all duration-200
                    hover:shadow-md hover:scale-[1.02] hover:border-primary/50
                    ${index % 2 === 0 ? 'bg-card' : 'bg-muted/20'}
                  `}
                >
                  <div className="flex items-start gap-2">
                    <div className={`
                      shrink-0 h-6 w-6 rounded flex items-center justify-center
                      ${currentTypeConfig?.bgColor || 'bg-primary/10'}
                    `}>
                      {currentTypeConfig && (
                        <currentTypeConfig.icon className={`h-3 w-3 ${currentTypeConfig.textColor}`} />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium line-clamp-2 leading-tight">
                        {getServiceName(service)}
                      </p>
                    </div>
                    <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                  </div>
                </Card>
              ))}
            </div>

            {/* View More Button */}
            {hasMore && (
              <div className="mt-6 text-center">
                <Button
                  onClick={handleViewMore}
                  variant="outline"
                  size="sm"
                  className="min-w-[160px]"
                >
                  {t('seeMore')}
                  <ArrowRight className="ml-2 h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </>
        )}

        {/* Empty State */}
        {!loading && servicesData && servicesData.services.length === 0 && (
          <Card className="p-8 text-center">
            <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-sm font-semibold mb-1">{t('empty')}</h3>
            <p className="text-xs text-muted-foreground">{t('emptyDescription')}</p>
          </Card>
        )}
      </div>
    </section>
  );
};

export default ServicesDirectory;
