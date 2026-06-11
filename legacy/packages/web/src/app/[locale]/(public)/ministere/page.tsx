'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Building2, Loader2, LayoutGrid, List, Search } from 'lucide-react';
import Breadcrumb from '@/components/ui/breadcrumb';
import { getMinistryDirectory, type MinistryItem } from '@/core/api/homepage';

// Ministry icon color palette (cycles through 8 colors)
const MINISTRY_COLORS = [
  'bg-blue-100 text-blue-600',
  'bg-emerald-100 text-emerald-600',
  'bg-purple-100 text-purple-600',
  'bg-orange-100 text-orange-600',
  'bg-pink-100 text-pink-600',
  'bg-cyan-100 text-cyan-600',
  'bg-amber-100 text-amber-600',
  'bg-rose-100 text-rose-600',
];

type ViewMode = 'kanban' | 'list';
type SortOption = 'name-asc' | 'name-desc' | 'count-desc';

export default function MinisterePage() {
  const params = useParams();
  const router = useRouter();
  const locale = (params?.locale as string) || 'es';
  const t = useTranslations('ministriesPage');
  const tCommon = useTranslations('common');

  const [ministries, setMinistries] = useState<MinistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>('count-desc');

  useEffect(() => {
    async function fetchMinistries() {
      try {
        setLoading(true);
        setError(null);

        // Fetch ministry directory from homepage API
        const result = await getMinistryDirectory(locale);
        setMinistries(result.ministries);
      } catch (err) {
        console.error('Failed to fetch ministries:', err);
        setError(t('errorLoading'));
      } finally {
        setLoading(false);
      }
    }

    fetchMinistries();
  }, [locale, t]);

  // Filter and sort ministries based on search query and sort option
  const filteredMinistries = useMemo(() => {
    let result = ministries;

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(ministry =>
        ministry.name?.toLowerCase().includes(query)
      );
    }

    // Sort
    const sorted = [...result];
    switch (sortOption) {
      case 'name-asc':
        sorted.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        break;
      case 'name-desc':
        sorted.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
        break;
      case 'count-desc':
        sorted.sort((a, b) => (b.service_count || 0) - (a.service_count || 0));
        break;
    }

    return sorted;
  }, [ministries, searchQuery, sortOption]);

  return (
    <div className="container mx-auto px-4 py-12">
      <Breadcrumb
        items={[{ label: t('title') }]}
        className="mb-6"
      />

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-4xl font-bold mb-2">{t('title')}</h1>
          <p className="text-lg text-muted-foreground">
            {t('description')}
          </p>
        </div>

        {!loading && ministries.length > 0 && (
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

      {/* Search and Sort */}
      {!loading && ministries.length > 0 && (
        <div className="mb-8 flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
            <Input
              type="text"
              placeholder={t('searchPlaceholder')}
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value);
                if (debounceRef.current) clearTimeout(debounceRef.current);
                debounceRef.current = setTimeout(() => setSearchQuery(e.target.value), 300);
              }}
              className="pl-10 pr-4 py-5"
            />
          </div>
          <Select value={sortOption} onValueChange={(value) => setSortOption(value as SortOption)}>
            <SelectTrigger className="w-full sm:w-[240px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="name-asc">{t('sortNameAsc')}</SelectItem>
              <SelectItem value="name-desc">{t('sortNameDesc')}</SelectItem>
              <SelectItem value="count-desc">{t('sortCountDesc')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {loading && (
        <div className="flex justify-center items-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-3 text-muted-foreground">{t('loading')}</span>
        </div>
      )}

      {error && !loading && (
        <div className="text-center py-12">
          <p className="text-destructive">{error}</p>
        </div>
      )}

      {!loading && !error && ministries.length === 0 && (
        <div className="text-center py-12">
          <Building2 className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">{t('noMinistries')}</p>
        </div>
      )}

      {!loading && !error && ministries.length > 0 && filteredMinistries.length === 0 && (
        <div className="text-center py-12">
          <Building2 className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">{t('noResults')}</p>
        </div>
      )}

      {/* Kanban View */}
      {!loading && !error && filteredMinistries.length > 0 && viewMode === 'kanban' && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredMinistries.map((ministry, index) => {
            const colorClass = MINISTRY_COLORS[index % MINISTRY_COLORS.length];
            return (
              <Card
                key={ministry.id}
                className="group hover:shadow-lg transition-all duration-300"
              >
                <div className="p-6">
                  <div className="flex items-start gap-4">
                    <div className={`p-3 rounded-lg ${colorClass}`}>
                      <Building2 className="h-6 w-6" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium line-clamp-2">
                        {ministry.name}
                      </h3>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-4 pt-4 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-amber-500 text-amber-600 hover:bg-amber-50 hover:text-amber-700"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/${locale}/ministere/${ministry.id}`);
                      }}
                    >
                      {t('viewMinistry')}
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/${locale}/services?ministry=${ministry.id}`);
                      }}
                    >
                      {ministry.service_count} {t('servicesConsult')}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* List View */}
      {!loading && !error && filteredMinistries.length > 0 && viewMode === 'list' && (
        <div className="space-y-4">
          {filteredMinistries.map((ministry, index) => {
            const colorClass = MINISTRY_COLORS[index % MINISTRY_COLORS.length];
            return (
              <Card
                key={ministry.id}
                className="group hover:shadow-md transition-all duration-300"
              >
                <div className="p-6 flex items-center gap-6">
                  <div className={`p-3 rounded-lg ${colorClass}`}>
                    <Building2 className="h-6 w-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium">
                      {ministry.name}
                    </h3>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-amber-500 text-amber-600 hover:bg-amber-50 hover:text-amber-700"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/${locale}/ministere/${ministry.id}`);
                      }}
                    >
                      {t('viewMinistry')}
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/${locale}/services?ministry=${ministry.id}`);
                      }}
                    >
                      {ministry.service_count} {t('servicesConsult')}
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
