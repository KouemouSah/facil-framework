'use client';

import { Calculator, FileSearch, Download, Clock } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { useTranslations } from 'next-intl';

export const FeaturesSection = () => {
  const t = useTranslations('features');

  const features = [
    {
      icon: FileSearch,
      title: t('intelligentSearch'),
      description: t('intelligentSearchDesc'),
    },
    {
      icon: Calculator,
      title: t('taxCalculator'),
      description: t('taxCalculatorDesc'),
    },
    {
      icon: Download,
      title: t('documents'),
      description: t('documentsDesc'),
    },
    {
      icon: Clock,
      title: t('upToDate'),
      description: t('upToDateDesc'),
    },
  ];

  return (
    <section className="py-16">
      <div className="container mx-auto px-4">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">{t('title')}</h2>
          <p className="text-muted-foreground max-w-2xl mx-auto">{t('description')}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="group hover:shadow-lg transition-all duration-300">
                <div className="p-6 space-y-4">
                  <div className="h-12 w-12 rounded-lg bg-primary flex items-center justify-center group-hover:scale-110 transition-transform">
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="font-semibold text-lg">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{feature.description}</p>
                </div>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default FeaturesSection;
