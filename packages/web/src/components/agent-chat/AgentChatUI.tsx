'use client';

/**
 * AgentChatUI — Unified chat interface for all LLM analyst agents.
 *
 * ChatGPT-like layout:
 *   ┌───────────────────────────────────┐
 *   │ [Briefing strip - collapsible]    │
 *   ├───────────────────────────────────┤
 *   │                                   │
 *   │  Conversation thread (scroll)     │
 *   │  ┌── User bubble ──────────────┐  │
 *   │  │ Question                    │  │
 *   │  └─────────────────────────────┘  │
 *   │  ┌── Agent bubble ─────────────┐  │
 *   │  │ KPIs / Tables / Summary     │  │
 *   │  │ Markdown analysis           │  │
 *   │  │ [tools] [export] [time]     │  │
 *   │  └─────────────────────────────┘  │
 *   │                                   │
 *   ├───────────────────────────────────┤
 *   │ [Quick action chips]              │
 *   │ [Input _______________] [Send ▶]  │
 *   └───────────────────────────────────┘
 *
 * History drawer (Sheet) opens from right.
 * Used by Treasury, Admin, and any future agent.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Send, Loader2, Wrench, Download, History,
  ChevronDown, ChevronUp, Sparkles, RefreshCw,
  User, Bot,
} from 'lucide-react';
import { renderMarkdown } from '@/core/utils/markdown';
import { ArtifactRenderer } from './ArtifactRenderer';
import type { AgentChatConfig, QAEntry, AgentBriefing } from './types';

let _idCounter = 0;
function nextId() { return `msg-${++_idCounter}-${Date.now()}`; }

// ── Briefing Strip ──────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  normal: 'bg-green-50 text-green-800 border-green-200',
  attention: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  urgent: 'bg-red-50 text-red-800 border-red-200',
};

function BriefingStrip({
  briefing,
  isLoading,
  labels,
}: {
  briefing?: AgentBriefing | null;
  isLoading?: boolean;
  labels?: { recommendations?: string };
}) {
  const [open, setOpen] = useState(false);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border bg-blue-50/50 border-blue-200">
        <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
        <span className="text-xs text-blue-700">Cargando briefing...</span>
      </div>
    );
  }

  if (!briefing) return null;

  const priorityClass = PRIORITY_COLORS[briefing.priority] || '';
  const oneLine = briefing.briefing.split('\n')[0].replace(/\*\*/g, '').slice(0, 140);
  const recs = briefing.recommendations ?? [];

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className={`rounded-lg border px-3 py-2 ${priorityClass}`}>
        <CollapsibleTrigger asChild>
          <button className="flex items-center gap-2 w-full text-left">
            <Badge variant="outline" className={`text-[10px] shrink-0 ${priorityClass}`}>
              {briefing.priority === 'urgent' ? 'Urgente' : briefing.priority === 'attention' ? 'Atención' : 'Normal'}
            </Badge>
            <span className="text-xs truncate flex-1">{oneLine}{!open && '...'}</span>
            {recs.length > 0 && (
              <Badge variant="secondary" className="text-[10px] shrink-0">
                {recs.length} {labels?.recommendations || 'rec.'}
              </Badge>
            )}
            {open ? <ChevronUp className="h-3.5 w-3.5 shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 shrink-0" />}
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div
            className="text-sm prose prose-sm max-w-none mt-2 pt-2 border-t"
            dangerouslySetInnerHTML={{ __html: renderMarkdown(briefing.briefing) }}
          />
          {recs.length > 0 && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                {labels?.recommendations || 'Acciones recomendadas'}
              </p>
              <ul className="space-y-1">
                {recs.map((rec, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <span className="mt-0.5 h-4 w-4 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[10px] font-bold shrink-0">
                      {i + 1}
                    </span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

// ── User Message Bubble ─────────────────────────────────────────

function UserBubble({ question }: { question: string }) {
  return (
    <div className="flex justify-end mb-3">
      <div className="flex items-start gap-2 max-w-[85%]">
        <div className="bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-2.5">
          <p className="text-sm">{question}</p>
        </div>
        <div className="h-7 w-7 rounded-full bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
          <User className="h-3.5 w-3.5 text-primary" />
        </div>
      </div>
    </div>
  );
}

// ── Agent Message Bubble ────────────────────────────────────────

function AgentBubble({
  entry,
  onRetry,
  isPending,
  labels,
  accentColor,
}: {
  entry: QAEntry;
  onRetry: (q: string) => void;
  isPending: boolean;
  labels: AgentChatConfig['labels'];
  accentColor?: string;
}) {
  const handleDownload = useCallback(() => {
    const ts = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-');
    const md = `# ${entry.question}\n\n_${entry.timestamp.toLocaleString()}_\n\n---\n\n${entry.response.answer}\n`;
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agent-${ts}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [entry]);

  const artifacts = entry.response.artifacts || [];
  const borderClass = entry.isError ? 'border-red-200 bg-red-50/30' : 'border-muted bg-muted/20';

  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-2 max-w-[90%] w-full">
        <div className={`h-7 w-7 rounded-full ${accentColor || 'bg-blue-100'} flex items-center justify-center shrink-0 mt-0.5`}>
          <Bot className="h-3.5 w-3.5 text-blue-700" />
        </div>
        <div className={`flex-1 rounded-2xl rounded-tl-sm border ${borderClass} overflow-hidden`}>
          {/* Artifacts inline */}
          {artifacts.length > 0 && (
            <div className="p-3 space-y-2 border-b bg-background/50">
              {artifacts.map((artifact, i) => (
                <ArtifactRenderer key={`art-${i}`} artifact={artifact} />
              ))}
            </div>
          )}

          {/* Markdown analysis */}
          <div className="px-4 py-3">
            <div
              className="text-sm prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(entry.response.answer) }}
            />
          </div>

          {/* Footer */}
          <div className="flex items-center gap-1.5 px-4 py-2 border-t bg-muted/30 flex-wrap">
            {entry.response.tools_used.length > 0 && (
              <div className="flex items-center gap-1">
                <Wrench className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground">
                  {labels.toolsUsed}: {entry.response.tools_used.join(', ')}
                </span>
              </div>
            )}
            <div className="ml-auto flex items-center gap-1">
              {entry.isError && (
                <Button
                  variant="ghost" size="sm"
                  className="h-6 px-2 text-[10px]"
                  onClick={() => onRetry(entry.question)}
                  disabled={isPending}
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  {labels.retry}
                </Button>
              )}
              {!entry.isError && (
                <Button
                  variant="ghost" size="sm"
                  className="h-6 px-2 text-[10px]"
                  onClick={handleDownload}
                >
                  <Download className="h-3 w-3 mr-1" />
                  {labels.download || 'MD'}
                </Button>
              )}
              <span className="text-[10px] text-muted-foreground ml-1">
                {entry.timestamp.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Loading Bubble ──────────────────────────────────────────────

function LoadingBubble({
  text,
  description,
  accentColor,
}: {
  text: string;
  description: string;
  accentColor?: string;
}) {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-2 max-w-[80%]">
        <div className={`h-7 w-7 rounded-full ${accentColor || 'bg-blue-100'} flex items-center justify-center shrink-0 mt-0.5`}>
          <Bot className="h-3.5 w-3.5 text-blue-700 animate-pulse" />
        </div>
        <div className="rounded-2xl rounded-tl-sm border border-blue-200 bg-blue-50/30 px-4 py-3">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
            <div>
              <p className="text-sm font-medium text-blue-800">{text}</p>
              <p className="text-xs text-blue-600">{description}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── History Drawer ───────────────────────────────────────────────

function HistoryDrawer({
  entries,
  onSelect,
  label,
}: {
  entries: QAEntry[];
  onSelect: (q: string) => void;
  label: string;
}) {
  if (entries.length === 0) return null;

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-1.5">
          <History className="h-3.5 w-3.5" />
          {label}
          <Badge variant="secondary" className="text-[10px] h-4 px-1 ml-0.5">
            {entries.length}
          </Badge>
        </Button>
      </SheetTrigger>
      <SheetContent side="right" className="w-80 sm:w-96">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <History className="h-4 w-4" />
            {label}
          </SheetTitle>
        </SheetHeader>
        <ScrollArea className="h-[calc(100vh-5rem)] mt-4">
          <div className="space-y-2 pr-2">
            {entries.map((entry) => (
              <button
                key={entry.id}
                className={`w-full text-left p-3 rounded-lg border hover:bg-accent/50 transition-colors ${
                  entry.isError ? 'border-red-200' : 'border-muted'
                }`}
                onClick={() => onSelect(entry.question)}
              >
                <p className="text-sm font-medium truncate">{entry.question}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-muted-foreground">
                    {entry.timestamp.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  {entry.response.tools_used.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      {entry.response.tools_used.length} tools
                    </span>
                  )}
                  {entry.isError && (
                    <Badge variant="destructive" className="text-[10px] h-4 px-1">Error</Badge>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                  {entry.response.answer.slice(0, 100)}...
                </p>
              </button>
            ))}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}

// ── Empty State ─────────────────────────────────────────────────

function EmptyState({
  icon: Icon,
  text,
  examples,
}: {
  icon?: typeof Sparkles;
  text: string;
  examples: string;
}) {
  const IconComp = Icon || Sparkles;
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center text-muted-foreground max-w-md">
        <IconComp className="h-12 w-12 mx-auto mb-4 opacity-30" />
        <p className="text-sm">{text}</p>
        <p className="text-xs mt-2 opacity-70">{examples}</p>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════

export function AgentChatUI({ config }: { config: AgentChatConfig }) {
  const [inputValue, setInputValue] = useState('');
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const sessionIdRef = useRef<string>(crypto.randomUUID());
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { mutation } = config;

  // Auto-scroll to bottom on new message
  useEffect(() => {
    if (scrollRef.current) {
      const el = scrollRef.current;
      // Small delay to let the DOM render
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [history.length, pendingQuestion]);

  const handleAsk = useCallback(
    async (question: string) => {
      if (!question.trim() || mutation.isPending) return;
      setInputValue('');
      setPendingQuestion(question);

      const lastSuccessful = history.find(
        (e) => !e.isError && e.response.tools_used.length > 0
      );
      const previousContext = lastSuccessful
        ? { question: lastSuccessful.question, tools_used: lastSuccessful.response.tools_used }
        : undefined;

      try {
        const response = await mutation.mutateAsync({
          question,
          previousContext,
          sessionId: sessionIdRef.current,
        });
        setHistory((prev) => [
          ...prev,
          { id: nextId(), question, response, timestamp: new Date() },
        ]);
      } catch {
        setHistory((prev) => [
          ...prev,
          {
            id: nextId(),
            question,
            response: { answer: config.errorMessage, tools_used: [], data: {} },
            timestamp: new Date(),
            isError: true,
          },
        ]);
      } finally {
        setPendingQuestion(null);
        // Refocus input
        requestAnimationFrame(() => inputRef.current?.focus());
      }
    },
    [mutation, history, config.errorMessage]
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleAsk(inputValue);
  };

  const handleHistorySelect = (question: string) => {
    setInputValue(question);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)]">
      {/* ── Briefing Strip ─────────────────────────────────────── */}
      {(config.briefing !== undefined || config.briefingLoading) && (
        <div className="shrink-0 mb-2">
          <BriefingStrip
            briefing={config.briefing}
            isLoading={config.briefingLoading}
            labels={config.labels}
          />
        </div>
      )}

      {/* ── Conversation Thread ────────────────────────────────── */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto px-1"
      >
        {history.length === 0 && !pendingQuestion && (
          <EmptyState
            icon={config.icon}
            text={config.emptyStateText}
            examples={config.emptyExamplesText}
          />
        )}

        {history.map((entry) => (
          <div key={entry.id}>
            <UserBubble question={entry.question} />
            <AgentBubble
              entry={entry}
              onRetry={handleAsk}
              isPending={mutation.isPending}
              labels={config.labels}
              accentColor={config.accentColor}
            />
          </div>
        ))}

        {/* Pending question + loading */}
        {pendingQuestion && (
          <>
            <UserBubble question={pendingQuestion} />
            <LoadingBubble
              text={config.analyzingText}
              description={config.analyzingDesc}
              accentColor={config.accentColor}
            />
          </>
        )}
      </div>

      {/* ── Bottom Bar: Quick Actions + Input ──────────────────── */}
      <div className="shrink-0 border-t pt-3 mt-2 space-y-2">
        {/* Quick Actions */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <div className="flex gap-1.5 flex-nowrap">
            {config.quickActions.map((action) => {
              const Icon = action.icon;
              return (
                <Button
                  key={action.label}
                  variant="outline"
                  size="sm"
                  className="shrink-0 h-7 text-xs gap-1"
                  onClick={() => handleAsk(action.question)}
                  disabled={mutation.isPending}
                >
                  <Icon className="h-3 w-3" />
                  {action.label}
                </Button>
              );
            })}
          </div>
          <div className="ml-auto shrink-0">
            <HistoryDrawer
              entries={history}
              onSelect={handleHistorySelect}
              label={config.labels.history}
            />
          </div>
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Input
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={config.placeholder}
            disabled={mutation.isPending}
            className="flex-1"
            autoComplete="off"
          />
          <Button
            type="submit"
            disabled={!inputValue.trim() || mutation.isPending}
            size="sm"
          >
            {mutation.isPending
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  );
}

export default AgentChatUI;
