/**
 * Accessibility Utilities for Chatbot
 * Helper functions and constants for ARIA, keyboard navigation, and screen readers
 *
 * @module chatbot/utils/accessibility
 * @author Claude Code
 * @date 2025-11-26
 *
 * WCAG 2.1 AA Compliance Features:
 * - ARIA labels and live regions
 * - Keyboard navigation
 * - Focus management
 * - Screen reader announcements
 */

// =============================================================================
// ARIA LIVE REGION UTILITIES
// =============================================================================

/**
 * Announce a message to screen readers
 * Uses an ARIA live region to make dynamic announcements
 */
export function announceToScreenReader(
  message: string,
  priority: 'polite' | 'assertive' = 'polite'
): void {
  // Find or create the announcement container
  let announcer = document.getElementById('chatbot-announcer')

  if (!announcer) {
    announcer = document.createElement('div')
    announcer.id = 'chatbot-announcer'
    announcer.setAttribute('aria-live', priority)
    announcer.setAttribute('aria-atomic', 'true')
    announcer.className = 'sr-only'
    announcer.style.cssText = `
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    `
    document.body.appendChild(announcer)
  }

  // Update the priority if needed
  announcer.setAttribute('aria-live', priority)

  // Clear and set the message (this triggers the announcement)
  announcer.textContent = ''
  // Small delay to ensure the change is detected
  setTimeout(() => {
    if (announcer) {
      announcer.textContent = message
    }
  }, 100)
}

/**
 * Announce new message arrival
 */
export function announceNewMessage(
  role: 'user' | 'assistant',
  content: string
): void {
  const roleLabel = role === 'user' ? 'You said' : 'Assistant replied'
  const truncatedContent =
    content.length > 100 ? `${content.substring(0, 100)}...` : content
  announceToScreenReader(`${roleLabel}: ${truncatedContent}`)
}

/**
 * Announce loading state
 */
export function announceLoading(isLoading: boolean): void {
  if (isLoading) {
    announceToScreenReader('Assistant is typing...', 'polite')
  }
}

/**
 * Announce error
 */
export function announceError(error: string): void {
  announceToScreenReader(`Error: ${error}`, 'assertive')
}

// =============================================================================
// KEYBOARD NAVIGATION
// =============================================================================

/**
 * Keyboard key codes
 */
export const KEYS = {
  ENTER: 'Enter',
  ESCAPE: 'Escape',
  SPACE: ' ',
  TAB: 'Tab',
  ARROW_UP: 'ArrowUp',
  ARROW_DOWN: 'ArrowDown',
  ARROW_LEFT: 'ArrowLeft',
  ARROW_RIGHT: 'ArrowRight',
  HOME: 'Home',
  END: 'End',
} as const

/**
 * Check if a key event is an activation key (Enter or Space)
 */
export function isActivationKey(event: KeyboardEvent | React.KeyboardEvent): boolean {
  return event.key === KEYS.ENTER || event.key === KEYS.SPACE
}

/**
 * Handle keyboard navigation for a list of items
 */
export function handleListKeyboardNavigation(
  event: KeyboardEvent | React.KeyboardEvent,
  currentIndex: number,
  totalItems: number,
  onSelect: (index: number) => void
): void {
  let newIndex = currentIndex

  switch (event.key) {
    case KEYS.ARROW_DOWN:
      event.preventDefault()
      newIndex = (currentIndex + 1) % totalItems
      break
    case KEYS.ARROW_UP:
      event.preventDefault()
      newIndex = (currentIndex - 1 + totalItems) % totalItems
      break
    case KEYS.HOME:
      event.preventDefault()
      newIndex = 0
      break
    case KEYS.END:
      event.preventDefault()
      newIndex = totalItems - 1
      break
    default:
      return
  }

  onSelect(newIndex)
}

// =============================================================================
// FOCUS MANAGEMENT
// =============================================================================

/**
 * Trap focus within a container (for modals/dialogs)
 */
export function trapFocus(container: HTMLElement): () => void {
  const focusableElements = container.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  )

  const firstElement = focusableElements[0]
  const lastElement = focusableElements[focusableElements.length - 1]

  const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key !== KEYS.TAB) return

    if (event.shiftKey) {
      // Shift + Tab
      if (document.activeElement === firstElement) {
        event.preventDefault()
        lastElement?.focus()
      }
    } else {
      // Tab
      if (document.activeElement === lastElement) {
        event.preventDefault()
        firstElement?.focus()
      }
    }
  }

  container.addEventListener('keydown', handleKeyDown)

  // Focus the first element
  firstElement?.focus()

  // Return cleanup function
  return () => {
    container.removeEventListener('keydown', handleKeyDown)
  }
}

/**
 * Store and restore focus (useful for opening/closing widgets)
 */
let previouslyFocusedElement: HTMLElement | null = null

export function storeFocus(): void {
  previouslyFocusedElement = document.activeElement as HTMLElement
}

export function restoreFocus(): void {
  if (previouslyFocusedElement && previouslyFocusedElement.focus) {
    previouslyFocusedElement.focus()
    previouslyFocusedElement = null
  }
}

// =============================================================================
// ARIA ATTRIBUTES HELPERS
// =============================================================================

/**
 * Generate ARIA attributes for a message
 */
export function getMessageAriaAttributes(
  role: 'user' | 'assistant',
  index: number
) {
  return {
    role: 'article' as const,
    'aria-label': `Message ${index + 1} from ${role === 'user' ? 'you' : 'assistant'}`,
    'aria-posinset': index + 1,
  }
}

/**
 * Generate ARIA attributes for the message list
 */
export function getMessageListAriaAttributes(totalMessages: number) {
  return {
    role: 'log' as const,
    'aria-label': 'Chat messages',
    'aria-live': 'polite' as const,
    'aria-relevant': 'additions' as const,
    'aria-atomic': false,
    'aria-setsize': totalMessages,
  }
}

/**
 * Generate ARIA attributes for chat input
 */
export function getChatInputAriaAttributes(
  isLoading: boolean,
  placeholder: string
) {
  return {
    role: 'textbox' as const,
    'aria-label': placeholder,
    'aria-disabled': isLoading,
    'aria-multiline': true,
    'aria-describedby': 'chat-input-description',
  }
}

/**
 * Generate ARIA attributes for send button
 */
export function getSendButtonAriaAttributes(
  isLoading: boolean,
  hasContent: boolean
) {
  return {
    'aria-label': isLoading ? 'Sending message...' : 'Send message',
    'aria-disabled': isLoading || !hasContent,
    'aria-busy': isLoading,
  }
}

/**
 * Generate ARIA attributes for suggestion chips
 */
export function getSuggestionChipAriaAttributes(
  suggestion: string,
  index: number,
  total: number
) {
  return {
    role: 'option' as const,
    'aria-label': `Suggestion ${index + 1} of ${total}: ${suggestion}`,
    'aria-posinset': index + 1,
    'aria-setsize': total,
  }
}

// =============================================================================
// SCREEN READER TEXT UTILITIES
// =============================================================================

/**
 * Generate screen reader only class
 */
export const srOnlyClass = 'sr-only'

/**
 * Create a visually hidden but screen reader accessible span
 */
export function srOnly(text: string): { text: string; className: string } {
  return {
    text,
    className: srOnlyClass,
  }
}

/**
 * Format timestamp for screen readers
 */
export function formatTimestampForSR(timestamp: string, locale: string = 'es'): string {
  const date = new Date(timestamp)
  return new Intl.DateTimeFormat(locale, {
    hour: 'numeric',
    minute: 'numeric',
    hour12: true,
  }).format(date)
}

// =============================================================================
// SKIP LINKS
// =============================================================================

/**
 * Create skip link for keyboard users
 */
export function createSkipLink(
  targetId: string,
  label: string
): HTMLAnchorElement {
  const skipLink = document.createElement('a')
  skipLink.href = `#${targetId}`
  skipLink.className =
    'sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md'
  skipLink.textContent = label
  return skipLink
}
