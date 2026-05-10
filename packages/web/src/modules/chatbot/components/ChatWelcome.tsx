/**
 * ChatWelcome — Logo + greeting + subtitle.
 * WelcomeSuggestions — Horizontal pill chips below input.
 *
 * Monographic Lucide icons (strokeWidth 1.5), warm stone palette,
 * 44px+ touch targets, hover transitions.
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import {
  Stamp,
  ScrollText,
  MapPin,
  Building2,
  Landmark,
  Info,
} from 'lucide-react';

interface ChatWelcomeProps {
  onSuggestionClick: (message: string) => void;
}

const QUICK_SUGGESTIONS = [
  { key: 'passport', icon: Stamp },
  { key: 'license', icon: ScrollText },
  { key: 'residence', icon: MapPin },
  { key: 'companies', icon: Building2 },
  { key: 'ministries', icon: Landmark },
  { key: 'what_is', icon: Info },
];

const ICON_PROPS = { className: 'w-4 h-4 shrink-0', strokeWidth: 1.5 } as const;

export const ChatWelcome: React.FC<ChatWelcomeProps> = () => {
  const t = useTranslations('chatbot');
  const [logoError, setLogoError] = useState(false);

  return (
    <div className="flex flex-col items-center px-6 max-w-3xl mx-auto w-full">
      {/* Logo with fallback — use img tag for reliability */}
      {!logoError ? (
        <img
          src="/logo_chat.png"
          alt="Facil"
          width={56}
          height={56}
          className="mb-3"
          onError={() => setLogoError(true)}
        />
      ) : (
        <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center mb-3">
          <span className="text-xl font-bold text-primary">F</span>
        </div>
      )}

      {/* Greeting — tight spacing to input */}
      <h1 className="text-2xl md:text-3xl font-semibold text-stone-800 dark:text-stone-100 mb-2 text-center tracking-tight">
        {t('chatPage.greeting')}
      </h1>
      <p className="text-sm text-stone-500 dark:text-stone-400 mb-6 text-center max-w-md leading-relaxed">
        {t('chatPage.subtitle')}
      </p>
    </div>
  );
};

/**
 * WelcomeSuggestions — Horizontal pill chips with hover animation.
 * Min height 40px (44px touch target with padding).
 */
export const WelcomeSuggestions: React.FC<{
  onSuggestionClick: (message: string) => void;
}> = ({ onSuggestionClick }) => {
  const t = useTranslations('chatbot');

  return (
    <div className="flex flex-wrap justify-center gap-2 px-4">
      {QUICK_SUGGESTIONS.map((item) => {
        const Icon = item.icon;
        return (
          <Button
            key={item.key}
            variant="outline"
            className="gap-2 text-xs text-stone-500 dark:text-stone-400 hover:text-stone-800 dark:hover:text-stone-100 hover:bg-stone-100 dark:hover:bg-stone-800 hover:border-stone-300 dark:hover:border-stone-600 rounded-full px-5 h-10 border-stone-200 dark:border-stone-700 bg-white/60 dark:bg-stone-800/60 backdrop-blur-sm transition-all duration-200 hover:shadow-sm"
            onClick={() => onSuggestionClick(t(`chatPage.suggestion_${item.key}`))}
          >
            <Icon {...ICON_PROPS} />
            <span>{t(`chatPage.suggestion_${item.key}`)}</span>
          </Button>
        );
      })}
    </div>
  );
};
