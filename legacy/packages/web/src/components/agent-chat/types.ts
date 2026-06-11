/**
 * Agent Chat UI — Shared types for the unified chat component.
 *
 * Any new agent only needs to provide AgentChatConfig to get the full chat UI.
 */

import type { LucideIcon } from 'lucide-react';
import type { UseMutationResult } from '@tanstack/react-query';

// ── Artifacts (from Treasury, reused by any agent) ──────────────

export interface TableArtifact {
  type: 'table';
  title: string;
  headers: string[];
  rows: string[][];
  alignments?: ('left' | 'right' | 'center')[];
}

export interface KpiGridArtifact {
  type: 'kpi_grid';
  title: string;
  metrics: { label: string; value: string; changePct?: number | null }[];
}

export interface SummaryArtifact {
  type: 'summary';
  title: string;
  content: string;
  severity?: 'info' | 'warning' | 'critical';
}

export type ArtifactData = TableArtifact | KpiGridArtifact | SummaryArtifact;

// ── Agent Response (universal) ──────────────────────────────────

export interface AgentResponse {
  answer: string;
  tools_used: string[];
  data: Record<string, unknown>;
  artifacts?: ArtifactData[];
}

// ── Briefing (optional, e.g. Treasury) ──────────────────────────

export interface AgentBriefing {
  briefing: string;
  priority: 'normal' | 'attention' | 'urgent';
  recommendations?: string[];
}

// ── Quick Action ────────────────────────────────────────────────

export interface QuickAction {
  label: string;
  question: string;
  icon: LucideIcon;
}

// ── Q&A History Entry ───────────────────────────────────────────

export interface QAEntry {
  id: string;
  question: string;
  response: AgentResponse;
  timestamp: Date;
  isError?: boolean;
}

// ── Agent Chat Config (what each agent provides) ────────────────

export interface AgentChatConfig {
  /** Agent display name */
  title: string;
  /** Short description below title */
  description: string;
  /** Input placeholder text */
  placeholder: string;
  /** Quick action buttons */
  quickActions: QuickAction[];
  /** Loading text */
  analyzingText: string;
  analyzingDesc: string;
  /** Error message */
  errorMessage: string;
  /** Empty state text */
  emptyStateText: string;
  emptyExamplesText: string;
  /** Labels */
  labels: {
    toolsUsed: string;
    retry: string;
    history: string;
    quickActionsMenu: string;
    recommendations?: string;
    download?: string;
  };
  /** Optional briefing data (auto-fetched) */
  briefing?: AgentBriefing | null;
  briefingLoading?: boolean;
  /** TanStack mutation for asking questions */
  mutation: UseMutationResult<AgentResponse, Error, {
    question: string;
    previousContext?: { question: string; tools_used: string[] };
    sessionId: string;
  }>;
  /** Agent accent color (tailwind classes) */
  accentColor?: string;
  /** Agent icon */
  icon?: LucideIcon;
}
