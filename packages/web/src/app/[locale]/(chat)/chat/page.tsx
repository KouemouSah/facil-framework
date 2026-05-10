import { getTranslations } from 'next-intl/server';
import { ChatPage } from '@/modules/chatbot/components/ChatPage';

const chatJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'WebApplication',
  name: 'Facil - Asistente IA',
  url: 'https://facil.gq/chat',
  applicationCategory: 'GovernmentService',
  operatingSystem: 'Web',
  description:
    'Asistente virtual IA para trámites fiscales y administrativos de Guinea Ecuatorial. Busca servicios, ministerios, empresas y oficinas.',
  provider: {
    '@type': 'GovernmentOrganization',
    name: 'FACIL - Plataforma Digital AI de Guinea Ecuatorial',
    url: 'https://facil.gq',
  },
  offers: {
    '@type': 'Offer',
    price: '0',
    priceCurrency: 'XAF',
  },
};

export async function generateMetadata({
  params: { locale },
}: {
  params: { locale: string };
}) {
  const t = await getTranslations({ locale, namespace: 'chatbot' });

  return {
    title: 'Facil - Asistente IA | Guinea Ecuatorial',
    description: t('chatPage.subtitle'),
    openGraph: {
      title: 'Facil - Asistente IA de Guinea Ecuatorial',
      description: t('chatPage.subtitle'),
      type: 'website',
      url: 'https://facil.gq/chat',
      siteName: 'Facil',
      images: [{ url: 'https://facil.gq/logo_chat.png', width: 512, height: 512 }],
    },
    twitter: {
      card: 'summary',
      title: 'Facil - Asistente IA',
      description: t('chatPage.subtitle'),
    },
    alternates: {
      canonical: `/${locale}/chat`,
      languages: { es: '/es/chat', fr: '/fr/chat', en: '/en/chat' },
    },
  };
}

export default function ChatRoute() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(chatJsonLd) }}
      />
      <ChatPage />
    </>
  );
}
