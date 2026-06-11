'use client';

import { FileCheck, ClipboardList, Bot } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { useTranslations } from 'next-intl';
import { useParams, useRouter } from 'next/navigation';

export const StatsSection = () => {
  const t = useTranslations('stats');
  const router = useRouter();
  const params = useParams();
  const locale = (params?.locale as string) || 'es';

  // Open chatbot function - triggers the chatbot widget
  const openChatbot = () => {
    // Dispatch a custom event that the ChatBot component listens to
    const event = new CustomEvent('openChatbot');
    window.dispatchEvent(event);
  };

  const ctas = [
    {
      icon: FileCheck,
      title: t('onlineDeclaration'),
      description: t('onlineDeclarationDesc'),
      onClick: () => router.push(`/${locale}/declarations`),
    },
    {
      icon: ClipboardList,
      title: t('trackDeclaration'),
      description: t('trackDeclarationDesc'),
      onClick: () => router.push(`/${locale}/dashboard/declarations`),
    },
    {
      icon: Bot,
      title: t('aiAssistant'),
      description: t('aiAssistantDesc'),
      onClick: openChatbot,
    },
  ];

  return (
    <section className="py-16 bg-muted/30">
      <div className="container mx-auto px-4">
        <h2 className="text-3xl font-bold text-center mb-4">{t('whyFacil')}</h2>
        <p className="text-center text-muted-foreground mb-12 max-w-2xl mx-auto">
          {t('whyFacilDesc')}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-4xl mx-auto">
          {ctas.map((cta, index) => {
            const Icon = cta.icon;
            return (
              <Card
                key={index}
                className="text-center p-6 hover:shadow-lg transition-shadow cursor-pointer"
                onClick={cta.onClick}
              >
                <div className="w-16 h-16 mx-auto mb-4 bg-primary/10 rounded-full flex items-center justify-center">
                  <Icon className="h-8 w-8 text-primary" />
                </div>
                <h3 className="text-lg font-semibold mb-2">{cta.title}</h3>
                <p className="text-sm text-muted-foreground">{cta.description}</p>
              </Card>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default StatsSection;
