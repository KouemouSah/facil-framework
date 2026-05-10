'use client';

import { Search, Calculator, BookOpen, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { getHomepageStats, type HomepageStats } from '@/core/api/homepage';

export const HeroSection = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [stats, setStats] = useState<HomepageStats | null>(null);
  const router = useRouter();
  const locale = useLocale();
  const t = useTranslations('hero');
  const tNav = useTranslations('nav');

  useEffect(() => {
    async function fetchStats() {
      try {
        const data = await getHomepageStats();
        setStats(data);
      } catch (err) {
        console.error('Failed to fetch stats for Hero:', err);
        // Fallback to default value if API fails
        setStats({
          total_services: 0,
          total_ministries: 0,
          total_categories: 0,
          total_sectors: 0,
          last_updated: new Date().toISOString(),
        });
      }
    }

    fetchStats();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/${locale}/services?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  const quickLinks = [
    {
      icon: Calculator,
      title: t('calculator'),
      description: t('calculatorDesc'),
      href: `/${locale}/calculateur`,
      color: 'text-white',
    },
    {
      icon: FileText,
      title: stats ? `${stats.total_services} ${tNav('services')}` : tNav('services'),
      description: t('servicesDesc'),
      href: `/${locale}/services`,
      color: 'text-white',
    },
    {
      icon: BookOpen,
      title: t('completeGuide'),
      description: t('completeGuideDesc'),
      href: `/${locale}/guide`,
      color: 'text-white',
    },
  ];

  return (
    <section className="relative overflow-hidden bg-primary py-20 lg:py-28">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-grid-white/10 [mask-image:linear-gradient(0deg,transparent,black)]"></div>

      <div className="container relative mx-auto px-4">
        <div className="mx-auto max-w-4xl text-center">
          {/* Badge */}
          <div className="mb-6 inline-flex items-center rounded-full border border-white/20 bg-white/10 px-4 py-1.5 text-sm text-white backdrop-blur-sm">
            <span className="mr-2">🇬🇶</span>
            <span>{t('badge')}</span>
          </div>

          {/* Main Title */}
          <h1 className="mb-6 text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
            {t('title')}
          </h1>

          {/* Subtitle */}
          <p className="mb-10 text-lg text-white/90 sm:text-xl">{t('subtitle')}</p>

          {/* Search Bar */}
          <form onSubmit={handleSearch} className="mb-12">
            <div className="mx-auto max-w-2xl">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    type="text"
                    placeholder={t('searchPlaceholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-12 pl-10 bg-white border-white/20 text-foreground placeholder:text-muted-foreground"
                  />
                </div>
                <Button type="submit" size="lg" className="h-12 bg-white text-primary hover:bg-white/90">
                  {t('searchButton')}
                </Button>
              </div>
            </div>
          </form>

          {/* Quick Links */}
          <div className="grid gap-4 sm:grid-cols-3">
            {quickLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Card
                  key={link.title}
                  className="group cursor-pointer border-white/20 bg-white/10 backdrop-blur-sm transition-all hover:bg-white/20 hover:shadow-lg"
                  onClick={() => router.push(link.href)}
                >
                  <div className="p-6 flex flex-col items-center text-center">
                    <Icon className={`mb-3 h-8 w-8 ${link.color}`} />
                    <h3 className="mb-1 font-semibold text-white">{link.title}</h3>
                    <p className="text-sm text-white/80">{link.description}</p>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};

export default HeroSection;
