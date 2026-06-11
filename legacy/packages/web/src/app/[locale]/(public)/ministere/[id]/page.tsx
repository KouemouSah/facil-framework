'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import Image from 'next/image';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Building2, ArrowLeft, FileText, FolderOpen, Layers, MapPin, Clock } from 'lucide-react';
import Breadcrumb from '@/components/ui/breadcrumb';
import { getMinistryDetails, type MinistryDetails } from '@/core/api/homepage';
import { getMinistryImageUrl } from '@/lib/firebase-storage';

// Sanitize HTML: strip script/iframe/object/embed tags and event handlers
function sanitizeHtml(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
    .replace(/<object[\s\S]*?<\/object>/gi, '')
    .replace(/<embed[\s\S]*?\/?>/gi, '')
    .replace(/<link[\s\S]*?\/?>/gi, '')
    .replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, '')
    .replace(/\bon\w+\s*=\s*[^\s>]*/gi, '')
    .replace(/javascript\s*:/gi, '')
    .replace(/data\s*:/gi, 'data-blocked:');
}

export default function MinistryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const locale = (params?.locale as string) || 'es';
  const ministryId = params?.id as string;
  const t = useTranslations('ministryDetail');

  const [ministry, setMinistry] = useState<MinistryDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  // Fetch ministry details
  useEffect(() => {
    async function fetchMinistryDetails() {
      if (!ministryId) return;

      try {
        setLoading(true);
        setError(null);
        setImageError(false);
        setImageUrl(null);

        const result = await getMinistryDetails(parseInt(ministryId), {
          language: locale,
        });

        setMinistry(result);

        // Load image URL from backend (returns signed URL)
        const url = await getMinistryImageUrl(parseInt(ministryId));
        if (url) {
          setImageUrl(url);
        } else {
          setImageError(true);
        }
      } catch (err) {
        console.error('Failed to fetch ministry details:', err);
        setError(t('errorLoading'));
      } finally {
        setLoading(false);
      }
    }

    fetchMinistryDetails();
  }, [ministryId, locale, t]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-12">
        <Skeleton className="h-8 w-64 mb-6" />
        <Skeleton className="h-12 w-96 mb-4" />
        <div className="grid gap-8 lg:grid-cols-2 mb-8">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  if (error || !ministry) {
    return (
      <div className="container mx-auto px-4 py-12">
        <div className="text-center py-12">
          <Building2 className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2">{error || t('notFound')}</h2>
          <Button onClick={() => router.push(`/${locale}/ministere`)} className="mt-4">
            <ArrowLeft className="h-4 w-4 mr-2" />
            {t('backToMinistries')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-12">
      {/* Breadcrumb */}
      <Breadcrumb
        items={[
          { label: t('ministries'), href: `/${locale}/ministere` },
          { label: ministry.name }
        ]}
        className="mb-6"
      />

      {/* Back Button */}
      <Button
        variant="ghost"
        onClick={() => router.push(`/${locale}/ministere`)}
        className="mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-2" />
        {t('back')}
      </Button>

      {/* Header with title */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold">{ministry.name}</h1>
      </div>

      {/* Main Content: 2 Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">

        {/* BLOCK 1 (LEFT): Ministry Image */}
        <div className="relative w-full aspect-[4/3] bg-muted rounded-lg overflow-hidden">
          {!imageError && imageUrl ? (
            <Image
              src={imageUrl}
              alt={ministry.name}
              fill
              className="object-cover"
              sizes="(max-width: 768px) 100vw, 50vw"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/5 to-primary/10">
              <Building2 className="h-24 w-24 text-muted-foreground/30" />
            </div>
          )}
        </div>

        {/* BLOCK 2 (RIGHT): Description + Stats */}
        <Card>
          <CardContent className="p-6 space-y-6">
            {/* Description */}
            <div>
              <h3 className="text-lg font-semibold mb-3">{t('description')}</h3>
              {ministry.description ? (
                <div
                  className="text-muted-foreground text-justify prose prose-sm max-w-none
                    prose-headings:text-foreground prose-headings:font-semibold
                    prose-h1:text-xl prose-h2:text-lg prose-h3:text-base
                    prose-p:my-2 prose-ul:my-2 prose-ol:my-2
                    prose-strong:text-foreground"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(ministry.description) }}
                />
              ) : (
                <p className="text-muted-foreground">{t('noDescription')}</p>
              )}
            </div>

            {/* Location and Opening Hours */}
            <div className="space-y-3 text-sm">
              <div className="flex items-start gap-3">
                <MapPin className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-medium">{t('location')}:</span>
                  <span className="text-muted-foreground ml-2">{t('comingSoon')}</span>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Clock className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-medium">{t('openingHours')}:</span>
                  <span className="text-muted-foreground ml-2">{t('comingSoon')}</span>
                </div>
              </div>
            </div>

            <Separator />

            {/* Stats with icons */}
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <FileText className="h-8 w-8 mx-auto text-primary mb-2" />
                <p className="text-2xl font-bold">{ministry.service_count}</p>
                <p className="text-xs text-muted-foreground">{t('services')}</p>
              </div>
              <div className="text-center">
                <FolderOpen className="h-8 w-8 mx-auto text-primary mb-2" />
                <p className="text-2xl font-bold">{ministry.category_count}</p>
                <p className="text-xs text-muted-foreground">{t('categories')}</p>
              </div>
              <div className="text-center">
                <Layers className="h-8 w-8 mx-auto text-primary mb-2" />
                <p className="text-2xl font-bold">{ministry.sector_count}</p>
                <p className="text-xs text-muted-foreground">{t('sectors')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
