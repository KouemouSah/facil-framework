import { getTranslations } from 'next-intl/server';
import {
  HeroSection,
  StatsSection,
  FeaturesSection,
  ServicesDirectory,
} from '@/modules/homepage/components';

/**
 * Homepage - Localized
 *
 * Routes:
 * - /es (Spanish - default)
 * - /fr (French)
 * - /en (English)
 */

export async function generateMetadata({ params: { locale } }: { params: { locale: string } }) {
  const t = await getTranslations({ locale, namespace: 'common' });
  const tHero = await getTranslations({ locale, namespace: 'hero' });
  const tMeta = await getTranslations({ locale, namespace: 'metadata' });

  return {
    title: t('appName') + ' - ' + t('appDescription'),
    description: tHero('subtitle'),
    openGraph: {
      title: t('appName') + ' - ' + tHero('title'),
      description: tHero('subtitle'),
      siteName: tMeta('siteName'),
      type: 'website',
    },
    alternates: {
      canonical: `/${locale}`,
      languages: {
        es: '/es',
        fr: '/fr',
        en: '/en',
      },
    },
  };
}

const organizationJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'GovernmentOrganization',
  name: 'FACIL - Plataforma Digital AI de Guinea Ecuatorial',
  url: 'https://facil.gq',
  logo: 'https://facil.gq/logo.png',
  description: 'Plataforma de trámites administrativos digitales con asistencia IA de Guinea Ecuatorial',
  areaServed: {
    '@type': 'Country',
    name: 'Equatorial Guinea',
  },
};

export default function HomePage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
      />
      <HeroSection />
      <StatsSection />
      <FeaturesSection />
      <ServicesDirectory />
    </>
  );
}
