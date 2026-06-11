/**
 * Chatbot types — aligned with backend ChatRequest/ChatResponse
 * Backend: app/modules/chatbot/models/chatbot.py
 */

export interface ChatMessage {
  id: string;
  text: string;
  isBot: boolean;
  timestamp: Date;
  suggestions?: string[];
  relatedServices?: RelatedService[];
}

export interface RelatedService {
  id: number;
  name: string;
  service_code?: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  language: 'es' | 'fr' | 'en';
  context?: Record<string, unknown>;
  history?: { role: 'user' | 'assistant'; content: string }[];
}

export interface FeedbackRequest {
  conversation_id: string;
  rating: number;
  feedback: string;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  suggestions: string[];
  related_services: { id: number; name: string; service_code?: string }[];
  follow_up_actions: string[];
  confidence: number;
  response_time: number;
  language: string;
  timestamp: string;
}
