'use client';

/**
 * Dashboard Chat — Full-width ChatGPT/Claude-inspired assistant.
 *
 * Pattern: welcome state → chat state (full width within dashboard layout).
 * Sidebar dashboard remains visible. Quick actions in welcome only.
 * History drawer slides from left. Agent settings via gear icon.
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import {
  Send, Loader2, History, ArrowDown, Plus,
  FileText, Calculator, Lightbulb, HelpCircle,
  FolderOpen, Clock, BarChart3, FileSearch,
  MessageSquare, ChevronRight, CreditCard,
  Rocket, BookOpen, Home, Car,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

import { useChat, useChatSettings } from '@/modules/chatbot/hooks';
import { MessageItem } from '@/modules/chatbot/components/MessageItem';
import { TypingIndicator } from '@/modules/chatbot/components/TypingIndicator';
import { SuggestionChips } from '@/modules/chatbot/components/SuggestionChips';
import { ExecutiveConfirmModal } from '@/modules/chatbot/components/ExecutiveConfirmModal';
import { chatbotApi } from '@/modules/chatbot/services/api';
import { AgentSettingsPanel } from '@/modules/user-documents/components/AgentSettingsPanel';
import type { ChatMessage, ChatAction } from '@/modules/chatbot/types';

// =============================================================================
// TYPES
// =============================================================================

interface QuickAction {
  icon: LucideIcon;
  titleKey: string;
  message: string;
  iconColor?: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const GENERAL_ACTIONS: QuickAction[] = [
  { icon: FileText, titleKey: 'askAboutDocuments', message: '', iconColor: 'text-blue-500' },
  { icon: Calculator, titleKey: 'askAboutCosts', message: '', iconColor: 'text-emerald-500' },
  { icon: Lightbulb, titleKey: 'askAboutProcedures', message: '', iconColor: 'text-amber-500' },
  { icon: HelpCircle, titleKey: 'askAboutServices', message: '', iconColor: 'text-violet-500' },
];

const VAULT_ACTIONS: QuickAction[] = [
  { icon: Clock, titleKey: 'vaultExpiring', message: '', iconColor: 'text-orange-500' },
  { icon: FileSearch, titleKey: 'vaultReadiness', message: '', iconColor: 'text-green-600' },
  { icon: BarChart3, titleKey: 'vaultStats', message: '', iconColor: 'text-blue-500' },
  { icon: FolderOpen, titleKey: 'vaultMissing', message: '', iconColor: 'text-purple-500' },
  { icon: CreditCard, titleKey: 'bundlePayment', message: '', iconColor: 'text-emerald-600' },
];

const WORKFLOW_OPTIONS = [
  { code: 'PASAPORTE_NUEVO', labelKey: 'wfPasaporteNuevo', icon: BookOpen, color: 'text-blue-500' },
  { code: 'PASAPORTE_RENOVACION', labelKey: 'wfPasaporteRenovacion', icon: BookOpen, color: 'text-blue-500' },
  { code: 'RESIDENCIA_PRIMERA_VEZ', labelKey: 'wfResidencia', icon: Home, color: 'text-green-600' },
  { code: 'CONDUCIR_NUEVO', labelKey: 'wfConducir', icon: Car, color: 'text-orange-500' },
  { code: 'FP_CARNET_FUNCIONARIO', labelKey: 'wfCarnetFuncionario', icon: CreditCard, color: 'text-purple-500' },
  { code: 'CONTRATO_SERVICIO', labelKey: 'wfContratoOnrc', icon: FileText, color: 'text-emerald-500' },
] as const;

// =============================================================================
// MAIN PAGE
// =============================================================================

export default function ChatPage() {
  const locale = useLocale();
  const t = useTranslations('chatbot');
  const tDash = useTranslations('dashboard');
  const tExec = useTranslations('chatbot.executive');

  useChatSettings({ persistToStorage: true });

  const {
    messages,
    isLoading,
    suggestions,
    sendMessage,
    pushAssistantMessage,
    clearChat,
    statusText,
    statusStep,
  } = useChat({
    language: (locale as 'es' | 'fr' | 'en') || 'es',
    persistToStorage: true,
  });

  const [input, setInput] = useState('');
  const [historyOpen, setHistoryOpen] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  // AgentSettingsPanel state — opened from chat action buttons or gear icon
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);
  const [highlightPerm, setHighlightPerm] = useState<string | undefined>(undefined);
  // ExecutiveConfirmModal state — opened by clicking a `confirm_executive`
  // action (Level 3 tools require per-action consent)
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<ChatAction | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const searchParams = useSearchParams();
  const hasMessages = messages.length > 0;
  const qSentRef = useRef(false);

  // Handler passed down to MessageItem: clicking "Activate permission"
  // opens the panel in-place without losing conversation context.
  const openAgentPanel = useCallback((permType?: string) => {
    setHighlightPerm(permType);
    setAgentPanelOpen(true);
  }, []);

  // Handler for Level 3 executive confirmation actions
  const handleConfirmExecutive = useCallback((action: ChatAction) => {
    setPendingAction(action);
    setConfirmModalOpen(true);
  }, []);

  // Called from the modal when the user clicks Confirm. POSTs directly to
  // /chatbot/execute-confirmed which redeems the single-use code in Redis
  // and runs the tool. Gemini is NOT re-invoked — we push the result as
  // an assistant message so the user sees it inline without burning tokens.
  const handleExecuteConfirmed = useCallback(
    async (code: string, _toolName: string) => {
      const response = await chatbotApi.executeConfirmed(code, locale);
      const resultPayload = (response.result ?? {}) as {
        status?: string;
        message?: string;
      };
      const statusLabel = resultPayload.status ?? 'unknown';
      const details = resultPayload.message ?? '';
      // Localized line varies by status — the modal already displayed the
      // summary pre-confirmation, so here we just acknowledge the outcome.
      const headerByStatus: Record<string, string> = {
        executed_stub: tExec('executedStub'),
        submitted: tExec('executedSuccess'),
        booked: tExec('executedSuccess'),
        error: tExec('executedError'),
      };
      const header = headerByStatus[statusLabel] ?? tExec('executedGeneric');
      pushAssistantMessage(`**${header}**\n\n${details}`.trim());
    },
    [locale, pushAssistantMessage, tExec],
  );

  // Resolve action messages (need t() which is only available in component)
  const generalActions = GENERAL_ACTIONS.map((a) => ({ ...a, message: t(a.titleKey) }));
  const vaultActions = VAULT_ACTIONS.map((a) => ({ ...a, message: t(a.titleKey) }));

  // Auto-send message from ?q= query param (e.g., from "Prepare with assistant" button)
  useEffect(() => {
    const q = searchParams?.get('q');
    if (q && !qSentRef.current && !isLoading) {
      qSentRef.current = true;
      sendMessage(q);
    }
  }, [searchParams, isLoading, sendMessage]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Track scroll position for "scroll to bottom" button
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollBtn(distanceFromBottom > 200);
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput('');
    await sendMessage(text);
  }, [input, isLoading, sendMessage]);

  const handleQuickAction = useCallback(async (message: string) => {
    if (isLoading) return;
    await sendMessage(message);
  }, [isLoading, sendMessage]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <div className="fixed inset-0 left-0 md:left-64 top-16 md:top-0 flex flex-col bg-background z-10">
      {/* ─── HEADER ─── */}
      <div className="flex items-center justify-between px-4 h-12 border-b bg-background/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-2">
          <Sheet open={historyOpen} onOpenChange={setHistoryOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <History className="h-4 w-4" strokeWidth={1.5} />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-72 p-0">
              <ConversationHistory onClose={() => setHistoryOpen(false)} />
            </SheetContent>
          </Sheet>
          <img src="/icon_facil.png" alt="Facil" className="h-6 w-6 object-contain" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
          <span className="font-semibold text-sm">Facil Assistant</span>
        </div>

        <div className="flex items-center gap-1">
          {hasMessages && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={clearChat}>
                    <Plus className="h-4 w-4" strokeWidth={1.5} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{t('newChat') || 'Nouveau chat'}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>

      {/* ─── CONTENT AREA ─── */}
      <div
        ref={scrollAreaRef}
        className="flex-1 overflow-y-auto relative"
        onScroll={handleScroll}
        style={{ scrollbarWidth: 'thin' }}
      >
        {!hasMessages ? (
          /* ─── WELCOME STATE ─── */
          <div className="flex flex-col items-center justify-center min-h-full px-4 py-8">
            <div className="max-w-2xl w-full space-y-8">
              {/* Logo + Greeting */}
              <div className="text-center space-y-3">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-white border border-border mx-auto">
                  <img src="/icon_facil.png" alt="Facil Assistant" className="h-10 w-10 object-contain" />
                </div>
                <h1 className="text-2xl font-semibold tracking-tight">
                  {t('welcomeTitle') || tDash('chatAssistant')}
                </h1>
                <p className="text-muted-foreground text-sm max-w-md mx-auto">
                  {t('welcomeMessage')}
                </p>
              </div>

              {/* Quick Actions Grid */}
              <div className="space-y-4">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider text-center">
                  {t('suggestions')}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {generalActions.map((action, i) => (
                    <QuickActionPill key={i} action={action} onClick={handleQuickAction} />
                  ))}
                </div>
              </div>

              {/* Vault Actions Grid */}
              <div className="space-y-4">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider text-center">
                  {t('vaultActionsTitle') || 'Mon coffre-fort'}
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {vaultActions.map((action, i) => (
                    <QuickActionPill key={i} action={action} onClick={handleQuickAction} />
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* ─── CHAT STATE ─── */
          <div className="max-w-6xl mx-auto w-full px-4 md:px-8 py-4 space-y-1">
            {messages.map((msg: ChatMessage, i: number) => (
              <MessageItem
                key={`${msg.timestamp}-${i}`}
                message={msg}
                locale={locale}
                onOpenAgentPanel={openAgentPanel}
                onConfirmExecutive={handleConfirmExecutive}
              />
            ))}

            {isLoading && (
              <TypingIndicator
                statusText={statusText ?? undefined}
                statusStep={statusStep ?? undefined}
              />
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Scroll to bottom FAB */}
        {showScrollBtn && hasMessages && (
          <button
            onClick={scrollToBottom}
            className="fixed bottom-24 right-8 z-10 p-2 rounded-full bg-background border shadow-md hover:bg-accent transition-colors"
            aria-label="Scroll to bottom"
          >
            <ArrowDown className="h-4 w-4" strokeWidth={1.5} />
          </button>
        )}
      </div>

      {/* ─── BOTTOM BAR ─── */}
      <div className="shrink-0 bg-background/80 backdrop-blur-sm">
        {/* Suggestion chips */}
        {suggestions.length > 0 && !isLoading && hasMessages && (
          <div className="px-4 pt-2">
            <SuggestionChips
              suggestions={suggestions}
              onSelect={(s) => sendMessage(s)}
            />
          </div>
        )}

        {/* Input area — "+" inside input, style Claude.ai */}
        <div className="max-w-4xl mx-auto w-full px-4 md:px-8 py-3">
          <div className="relative flex items-end rounded-2xl border bg-background focus-within:ring-2 focus-within:ring-primary/50 focus-within:border-primary">
            {/* "+" button INSIDE input, left side */}
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="flex items-center justify-center h-8 w-8 ml-2 mb-2 rounded-full hover:bg-accent transition-colors shrink-0 text-muted-foreground hover:text-foreground"
                >
                  <Plus className="h-5 w-5" strokeWidth={1.5} />
                </button>
              </PopoverTrigger>
              <PopoverContent side="top" align="start" className="w-72 p-2">
                <p className="text-xs font-medium text-muted-foreground px-2 py-1">{t('suggestions')}</p>
                <div className="space-y-0.5">
                  {[...generalActions, ...vaultActions].map((action, i) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={i}
                        onClick={() => { handleQuickAction(action.message); }}
                        className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-lg text-left text-sm hover:bg-accent transition-colors"
                      >
                        <Icon className={`h-4 w-4 shrink-0 ${action.iconColor ?? 'text-primary'}`} strokeWidth={1.5} />
                        <span className="truncate">{t(action.titleKey)}</span>
                      </button>
                    );
                  })}
                </div>
              </PopoverContent>
            </Popover>

            {/* Agent launch button — between "+" and textarea */}
            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="flex items-center justify-center h-8 w-8 mb-2 rounded-full hover:bg-accent transition-colors shrink-0 text-muted-foreground hover:text-primary"
                  title={t('launchAgent') || 'Iniciar un tramite'}
                >
                  <Rocket className="h-4 w-4" strokeWidth={1.5} />
                </button>
              </PopoverTrigger>
              <PopoverContent side="top" align="start" className="w-80 p-3">
                <p className="text-sm font-medium mb-2">{t('launchAgent') || 'Preparar una demarche'}</p>
                <p className="text-xs text-muted-foreground mb-3">{t('launchAgentDesc') || 'El asistente preparara su solicitud automaticamente'}</p>
                <div className="space-y-2">
                  {WORKFLOW_OPTIONS.map((wf) => (
                    <button
                      key={wf.code}
                      onClick={() => {
                        handleQuickAction(`${t('prepareRequest')} ${t(wf.labelKey)}`);
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border text-left text-sm hover:bg-accent hover:border-primary/30 transition-all"
                    >
                      <wf.icon className={`h-4 w-4 shrink-0 ${wf.color}`} strokeWidth={1.5} />
                      <span className="truncate">{t(wf.labelKey)}</span>
                    </button>
                  ))}
                </div>
              </PopoverContent>
            </Popover>

            {/* Textarea */}
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('inputPlaceholder')}
              disabled={isLoading}
              rows={1}
              className="flex-1 resize-none bg-transparent px-2 py-3.5 text-sm
                         focus:outline-none disabled:opacity-50
                         min-h-[52px] max-h-[160px]
                         placeholder:text-muted-foreground/60"
              style={{ scrollbarWidth: 'thin' }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
              }}
            />

            {/* Send button INSIDE input, right side */}
            <Button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              size="icon"
              className="mr-2 mb-2 h-8 w-8 rounded-lg shrink-0"
            >
              {isLoading
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Send className="h-4 w-4" />
              }
            </Button>
          </div>
        </div>
      </div>

      {/* ─── Agent Settings Panel — opened from MessageItem action buttons ─── */}
      <AgentSettingsPanel
        open={agentPanelOpen}
        onOpenChange={(open) => {
          setAgentPanelOpen(open);
          if (!open) setHighlightPerm(undefined);
        }}
        initialHighlightPermission={highlightPerm}
      />

      {/* ─── Executive Confirm Modal — Level 3 per-action consent ─── */}
      <ExecutiveConfirmModal
        open={confirmModalOpen}
        onOpenChange={(open) => {
          setConfirmModalOpen(open);
          if (!open) setPendingAction(null);
        }}
        summary={pendingAction?.summary}
        confirmationCode={pendingAction?.confirmation_code}
        toolName={pendingAction?.tool_name}
        onConfirm={handleExecuteConfirmed}
      />
    </div>
  );
}

// =============================================================================
// QUICK ACTION PILL
// =============================================================================

function QuickActionPill({
  action,
  onClick,
}: {
  action: QuickAction;
  onClick: (message: string) => void;
}) {
  const t = useTranslations('chatbot');
  const Icon = action.icon;

  return (
    <button
      onClick={() => onClick(action.message)}
      className="flex items-center gap-3 p-3 rounded-xl border bg-background
                 hover:bg-accent hover:border-primary/30 hover:shadow-sm
                 transition-all duration-150 text-left group"
    >
      <div className={`shrink-0 ${action.iconColor ?? 'text-primary'}`}>
        <Icon className="h-4 w-4" strokeWidth={1.5} />
      </div>
      <span className="text-sm font-medium truncate group-hover:text-primary transition-colors">
        {t(action.titleKey)}
      </span>
    </button>
  );
}

// =============================================================================
// CONVERSATION HISTORY (Sheet content)
// =============================================================================

function ConversationHistory({ onClose }: { onClose: () => void }) {
  const t = useTranslations('chatbot');

  // For now, show current conversation info.
  // Multi-conversation support can be added later.
  return (
    <div className="flex flex-col h-full">
      <SheetHeader className="px-4 py-3 border-b">
        <SheetTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4" strokeWidth={1.5} />
          {t('conversationHistory') || 'Historique'}
        </SheetTitle>
      </SheetHeader>

      <ScrollArea className="flex-1 px-3 py-2">
        {/* Current conversation */}
        <div className="space-y-1">
          <button
            className="w-full flex items-center gap-3 p-3 rounded-lg bg-accent/50 text-left"
            onClick={onClose}
          >
            <MessageSquare className="h-4 w-4 text-primary shrink-0" strokeWidth={1.5} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {t('currentConversation') || 'Conversation actuelle'}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('active') || 'Active'}
              </p>
            </div>
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" strokeWidth={1.5} />
          </button>
        </div>

        <Separator className="my-3" />

        <p className="text-xs text-muted-foreground text-center py-4">
          {t('historyComingSoon') || 'L\'historique multi-conversations sera disponible prochainement.'}
        </p>
      </ScrollArea>
    </div>
  );
}
