/**
 * Chatbot React Hook — aligned with web useChat.ts
 *
 * Key alignment points with web:
 * - History: last 10 messages EXCLUDING current message
 * - Language: passed directly (no extra instructions — backend handles it)
 * - ConversationId: undefined on first call, reused after
 * - Suggestions: extracted from response.suggestions
 */

import { useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { MMKV } from 'react-native-mmkv';

import { sendChatMessage } from './chatbot-api';
import type { ChatMessage, ChatResponse } from '../types/chatbot.types';

// Persistence via MMKV (sync, fast).
let storage: MMKV | null = null;
try {
  storage = new MMKV({ id: 'chatbot-persistence' });
} catch {
  // MMKV unavailable (e.g. JSI not ready in tests) — persistence disabled
}

let messageCounter = 0;
function nextId(): string {
  messageCounter += 1;
  return `msg_${Date.now()}_${messageCounter}`;
}

function loadPersistedMessages(): ChatMessage[] {
  if (!storage) return [];
  try {
    const raw = storage.getString('messages');
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return parsed.map((m: any) => ({ ...m, timestamp: new Date(m.timestamp) }));
  } catch { return []; }
}

function persistMessages(messages: ChatMessage[], conversationId?: string) {
  if (!storage) return;
  try {
    storage.set('messages', JSON.stringify(messages.slice(-50))); // Keep last 50
    if (conversationId) storage.set('conversationId', conversationId);
  } catch { /* best-effort */ }
}

export function useChatbot() {
  const { i18n } = useTranslation();
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadPersistedMessages());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const conversationIdRef = useRef<string | undefined>(
    storage?.getString('conversationId') || undefined
  );

  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      setError(null);

      // Add user message to local state
      const userMsg: ChatMessage = {
        id: nextId(),
        text: text.trim(),
        isBot: false,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      try {
        const lang = (i18n.language || 'es') as 'es' | 'fr' | 'en';

        // Build history: last 10 messages EXCLUDING current (same as web useChat.ts)
        // Web: history.length > 1 ? history.slice(0, -1) : undefined
        const allMessages = [...messages, userMsg];
        const historyRaw = allMessages
          .slice(-10)
          .map((m) => ({
            role: (m.isBot ? 'assistant' : 'user') as 'user' | 'assistant',
            content: m.text,
          }));
        // Exclude the current message (last one) — web does slice(0, -1)
        const history = historyRaw.length > 1 ? historyRaw.slice(0, -1) : undefined;

        const response: ChatResponse = await sendChatMessage({
          message: text.trim(),
          conversation_id: conversationIdRef.current,
          language: lang,
          history,
        });

        // Store conversation_id for continuity
        if (response.conversation_id) {
          conversationIdRef.current = response.conversation_id;
        }

        // Add bot response with suggestions and related services
        const botMsg: ChatMessage = {
          id: nextId(),
          text: response.response,
          isBot: true,
          timestamp: new Date(),
          suggestions: response.suggestions?.length > 0 ? response.suggestions : undefined,
          relatedServices:
            response.related_services?.length > 0
              ? response.related_services.map((s) => ({
                  id: s.id,
                  name: s.name,
                  service_code: s.service_code,
                }))
              : undefined,
        };
        setMessages((prev) => {
          const updated = [...prev, botMsg];
          persistMessages(updated, conversationIdRef.current);
          return updated;
        });
      } catch (err: any) {
        const status = err?.response?.status;
        if (status === 429) {
          setError('rate_limited');
        } else {
          setError('send_failed');
        }
      } finally {
        setIsLoading(false);
      }
    },
    [messages, isLoading, i18n.language],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    conversationIdRef.current = undefined;
    setError(null);
    if (storage) {
      storage.delete('messages');
      storage.delete('conversationId');
    }
  }, []);

  return { messages, isLoading, error, send, clearChat };
}
