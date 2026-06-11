/**
 * Chatbot API Service
 *
 * POST /chatbot/chat — works without authentication (optional auth).
 * Rate limited: 10 req/min anonymous, 30 req/min authenticated.
 * Includes retry with backoff for Cloud Run cold starts (~5-10s).
 */

import { apiPost } from '@core/api/client';
import { API_ENDPOINTS } from '@core/api/endpoints';
import { logger } from '@core/logging/logger';
import type { ChatRequest, ChatResponse, FeedbackRequest } from '../types/chatbot.types';

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 2000;

export async function sendChatMessage(req: ChatRequest): Promise<ChatResponse> {
  let lastError: any;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await apiPost<ChatResponse>(API_ENDPOINTS.chatbot.chat, req);
    } catch (err: any) {
      lastError = err;
      const status = err?.response?.status;

      // Don't retry on client errors (4xx) — only on server/network errors
      if (status && status >= 400 && status < 500) {
        throw err;
      }

      // Wait before retry (exponential backoff)
      if (attempt < MAX_RETRIES) {
        logger.warn('Chatbot', `Attempt ${attempt + 1} failed, retrying in ${RETRY_DELAY_MS * (attempt + 1)}ms`);
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * (attempt + 1)));
      }
    }
  }

  throw lastError;
}

/** POST /chatbot/feedback — best-effort, non-blocking */
export async function submitFeedback(req: FeedbackRequest): Promise<void> {
  try {
    await apiPost(API_ENDPOINTS.chatbot.feedback, req);
  } catch {
    // Best-effort — never fail the UI
  }
}
