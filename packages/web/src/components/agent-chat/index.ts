/**
 * Agent Chat UI — Barrel export.
 *
 * Usage for any new agent:
 *   1. Import { AgentChatUI, AgentChatConfig } from '@/components/agent-chat'
 *   2. Provide a config object with mutation, quick actions, labels, etc.
 *   3. Done — full ChatGPT-like UI with artifacts, history drawer, briefing.
 */

export { AgentChatUI } from './AgentChatUI';
export { ArtifactRenderer } from './ArtifactRenderer';
export type {
  AgentChatConfig,
  AgentResponse,
  AgentBriefing,
  QAEntry,
  QuickAction,
  ArtifactData,
  TableArtifact,
  KpiGridArtifact,
  SummaryArtifact,
} from './types';
