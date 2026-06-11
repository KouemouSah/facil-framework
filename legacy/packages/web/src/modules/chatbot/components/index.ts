/**
 * Chatbot Components Exports
 * Centralized exports for all chatbot UI components
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 */

// Main Chat Widget
export { ChatWidget } from './ChatWidget'
export type { ChatWidgetProps } from '../types'

// Message Components
export { MessageList } from './MessageList'
export type { MessageListProps } from './MessageList'

export { MessageItem } from './MessageItem'
export type { MessageItemProps } from './MessageItem'

// Input Components
export { ChatInput } from './ChatInput'
export type { ChatInputProps } from './ChatInput'

// Feedback Components
export { TypingIndicator } from './TypingIndicator'

export { SuggestionChips } from './SuggestionChips'
export type { SuggestionChipsProps } from './SuggestionChips'

export { RelatedServices } from './RelatedServices'
export type { RelatedServicesProps } from './RelatedServices'

// Settings Components
export { ChatSettingsPanel } from './ChatSettingsPanel'
export type { ChatSettingsPanelProps } from './ChatSettingsPanel'

// Error Handling Components
export {
  ChatErrorBoundary,
  ChatErrorDisplay,
  NetworkError,
  RateLimitError,
} from './ChatErrorBoundary'

// Chat-First Page Components
export { ChatPage } from './ChatPage'
export { ChatSidebar } from './ChatSidebar'
export { ChatWelcome, WelcomeSuggestions } from './ChatWelcome'
