/**
 * ChatPage — Claude.ai-inspired chat-first experience.
 *
 * Fixes applied:
 * 1. Input glassmorphism (no double border)
 * 2. Smooth transitions welcome ↔ chat (animate-in)
 * 3. Warm stone palette consistent across page
 * 4. Footer hidden on mobile
 * 5. Larger touch targets (44px+ on mobile)
 * 6. Dark mode cohesive
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';
import {
  Menu,
  Globe,
  Trash2,
  Square,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

import { useChat } from '../hooks/useChat';
import { useChatSettings } from '../hooks/useChatSettings';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';
import { TypingIndicator } from './TypingIndicator';
import { SuggestionChips } from './SuggestionChips';
import { ChatSidebar } from './ChatSidebar';
import { ChatWelcome, WelcomeSuggestions } from './ChatWelcome';

// =============================================================================
// COMPONENT
// =============================================================================

export const ChatPage: React.FC = () => {
  const locale = useLocale();
  const t = useTranslations('chatbot');
  const { settings, updateSettings } = useChatSettings();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const {
    messages,
    isLoading,
    suggestions,
    sendMessage,
    clearChat,
    statusText,
    statusStep,
  } = useChat({
    language: (locale as 'es' | 'fr' | 'en') || settings.language || 'es',
    persistToStorage: true,
  });

  const hasMessages = messages.length > 0;

  const handleSuggestionClick = useCallback(
    (message: string) => {
      sendMessage(message);
      setMobileMenuOpen(false);
    },
    [sendMessage]
  );

  const router = useRouter();
  const pathname = usePathname();

  const handleLanguageChange = (lang: 'es' | 'fr' | 'en') => {
    updateSettings({ language: lang });
    // Navigate to the same page in the new locale
    const newPath = pathname.replace(/^\/(es|fr|en)/, `/${lang}`);
    router.push(newPath);
  };

  return (
    <div className="flex h-full bg-stone-50 dark:bg-stone-900">
      {/* ── Desktop Sidebar (collapsible) ────────────────────────── */}
      <ChatSidebar
        className="hidden md:flex"
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* ── Main Chat Area ───────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0 relative">

        {/* ── Top bar ────────────────────────────────────────────── */}
        <div className="absolute top-0 right-0 left-0 z-10 flex items-center justify-between px-3 h-11">
          {/* Mobile menu */}
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="md:hidden w-9 h-9"
                aria-label="Menu"
              >
                <Menu className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <ChatSidebar
                expanded
                onNavigate={() => setMobileMenuOpen(false)}
              />
            </SheetContent>
          </Sheet>

          {/* Right controls */}
          <div className="flex items-center gap-0.5 ml-auto">
            {hasMessages && (
              <Button
                variant="ghost"
                size="icon"
                className="w-9 h-9 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 transition-colors"
                onClick={clearChat}
                aria-label={t('clearChat')}
              >
                <Trash2 className="w-[18px] h-[18px]" strokeWidth={1.5} />
              </Button>
            )}

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-stone-400 hover:text-stone-700 dark:hover:text-stone-200 h-9 px-2 transition-colors"
                >
                  <Globe className="w-[18px] h-[18px] mr-1" strokeWidth={1.5} />
                  {(settings.language || locale || 'es').toUpperCase()}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-[120px]">
                {(['es', 'fr', 'en'] as const).map((lang) => (
                  <DropdownMenuItem
                    key={lang}
                    onClick={() => handleLanguageChange(lang)}
                    className={settings.language === lang ? 'bg-stone-100 dark:bg-stone-800' : ''}
                  >
                    {lang === 'es' ? 'Español' : lang === 'fr' ? 'Français' : 'English'}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        {/* ── Content ────────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden min-h-0">
          {hasMessages ? (
            /* ── Chat State ─────────────────────────────────────── */
            <div className="flex-1 flex flex-col min-h-0">
              {/* Messages — min-h-0 is CRITICAL for nested flex scroll */}
              <div className="flex-1 overflow-y-auto pt-12 pb-2 min-h-0" style={{ scrollbarWidth: 'thin', scrollbarColor: '#a8a29e transparent' }}>
                <div className="max-w-3xl mx-auto w-full px-4">
                  <MessageList
                    messages={messages}
                    isLoading={isLoading}
                    locale={locale}
                  />
                  {isLoading && (
                    <div className="py-3">
                      <TypingIndicator statusText={statusText ?? undefined} statusStep={statusStep ?? undefined} />
                    </div>
                  )}
                </div>
              </div>

              {/* AI suggestions */}
              {suggestions.length > 0 && !isLoading && (
                <div className="max-w-3xl mx-auto w-full px-4 pb-2">
                  <SuggestionChips
                    suggestions={suggestions}
                    onSelect={handleSuggestionClick}
                  />
                </div>
              )}

              {/* Stop button when loading */}
              {isLoading && (
                <div className="flex justify-center pb-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 text-xs rounded-full border-stone-300 dark:border-stone-600 text-stone-500 hover:text-stone-800 h-8 px-4"
                    onClick={clearChat}
                  >
                    <Square className="w-3 h-3 fill-current" strokeWidth={1.5} />
                    {locale === 'fr' ? 'Arrêter' : locale === 'en' ? 'Stop' : 'Detener'}
                  </Button>
                </div>
              )}

              {/* Input — single clean box */}
              <div className="shrink-0 px-4 pb-3">
                <div className="max-w-3xl mx-auto w-full">
                  <ChatInput
                    onSend={sendMessage}
                    isLoading={isLoading}
                    placeholder={t('chatPage.input_placeholder')}
                    className="border border-stone-200 dark:border-stone-700 shadow-sm bg-white dark:bg-stone-800 rounded-2xl"
                  />
                </div>
              </div>
            </div>
          ) : (
            /* ── Welcome State ──────────────────────────────────── */
            <div className="flex-1 flex flex-col justify-center animate-in fade-in duration-500 pb-12">
              {/* Logo + Greeting */}
              <ChatWelcome onSuggestionClick={handleSuggestionClick} />

              {/* Input — single clean box, no wrapper (like claude.ai) */}
              <div className="max-w-3xl mx-auto w-full px-6 mb-4">
                <ChatInput
                  onSend={sendMessage}
                  isLoading={isLoading}
                  placeholder={t('chatPage.input_placeholder')}
                  className="border border-stone-200 dark:border-stone-700 shadow-sm bg-white dark:bg-stone-800 rounded-2xl"
                />
              </div>

              {/* Suggestion chips */}
              <div className="mb-4">
                <WelcomeSuggestions onSuggestionClick={handleSuggestionClick} />
              </div>
            </div>
          )}
        </div>

        {/* ── Footer (desktop only) ──────────────────────────────── */}
        <div className="hidden md:block text-center py-1.5 shrink-0">
          <p className="text-[10px] text-stone-400 dark:text-stone-500">
            © 2026 Facil - Plataforma Digital AI de Tramites. Todos los derechos reservados.
          </p>
        </div>
      </div>
    </div>
  );
};
