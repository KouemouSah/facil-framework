/**
 * ChatErrorBoundary Component
 * Error boundary for graceful error handling in chat components
 *
 * @module chatbot/components
 * @author Claude Code
 * @date 2025-11-26
 *
 * Features:
 * - Catches JavaScript errors in child components
 * - Displays user-friendly error message
 * - Retry mechanism
 * - Error logging
 */

'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertCircle, RefreshCw, MessageCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

// =============================================================================
// TYPES
// =============================================================================

interface ChatErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  onRetry?: () => void
}

interface ChatErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

// =============================================================================
// ERROR BOUNDARY CLASS COMPONENT
// =============================================================================

export class ChatErrorBoundary extends Component<
  ChatErrorBoundaryProps,
  ChatErrorBoundaryState
> {
  constructor(props: ChatErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<ChatErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console in development
    console.error('ChatErrorBoundary caught an error:', error, errorInfo)

    // Update state with error info
    this.setState({ errorInfo })

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
  }

  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    })

    if (this.props.onRetry) {
      this.props.onRetry()
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <Card className="m-4 border-destructive/50 bg-destructive/5">
          <CardContent className="p-6">
            <div className="flex flex-col items-center text-center space-y-4">
              <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
                <AlertCircle className="h-6 w-6 text-destructive" />
              </div>

              <div className="space-y-2">
                <h3 className="font-semibold text-lg text-destructive">
                  Something went wrong
                </h3>
                <p className="text-sm text-muted-foreground max-w-md">
                  We encountered an error while loading the chat. Please try again
                  or contact support if the problem persists.
                </p>
              </div>

              {/* Error details in development */}
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <details className="w-full text-left">
                  <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                    Technical Details
                  </summary>
                  <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto">
                    {this.state.error.message}
                    {this.state.errorInfo?.componentStack}
                  </pre>
                </details>
              )}

              <div className="flex gap-2">
                <Button
                  onClick={this.handleRetry}
                  variant="default"
                  className="gap-2"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try Again
                </Button>
                <Button
                  variant="outline"
                  onClick={() => window.location.reload()}
                  className="gap-2"
                >
                  <MessageCircle className="h-4 w-4" />
                  Reload Page
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )
    }

    return this.props.children
  }
}

// =============================================================================
// FUNCTIONAL ERROR DISPLAY COMPONENT
// =============================================================================

interface ChatErrorDisplayProps {
  error: string | Error
  onRetry?: () => void
  onDismiss?: () => void
  className?: string
}

export const ChatErrorDisplay: React.FC<ChatErrorDisplayProps> = ({
  error,
  onRetry,
  onDismiss,
  className = '',
}) => {
  const errorMessage = typeof error === 'string' ? error : error.message

  return (
    <div
      className={`flex items-start gap-3 p-3 bg-destructive/10 border border-destructive/20 rounded-lg ${className}`}
      role="alert"
      aria-live="assertive"
    >
      <AlertCircle
        className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5"
        aria-hidden="true"
      />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-destructive font-medium">Error</p>
        <p className="text-sm text-muted-foreground mt-1">{errorMessage}</p>

        {(onRetry || onDismiss) && (
          <div className="flex gap-2 mt-2">
            {onRetry && (
              <Button
                size="sm"
                variant="outline"
                onClick={onRetry}
                className="h-7 text-xs gap-1"
              >
                <RefreshCw className="h-3 w-3" />
                Retry
              </Button>
            )}
            {onDismiss && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onDismiss}
                className="h-7 text-xs"
              >
                Dismiss
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// NETWORK ERROR COMPONENT
// =============================================================================

interface NetworkErrorProps {
  onRetry?: () => void
  className?: string
}

export const NetworkError: React.FC<NetworkErrorProps> = ({
  onRetry,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center text-center p-6 ${className}`}
      role="alert"
      aria-live="polite"
    >
      <div className="h-16 w-16 rounded-full bg-yellow-100 dark:bg-yellow-900/20 flex items-center justify-center mb-4">
        <svg
          className="h-8 w-8 text-yellow-600 dark:text-yellow-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824 2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3"
          />
        </svg>
      </div>
      <h3 className="font-semibold text-lg mb-2">Connection Lost</h3>
      <p className="text-sm text-muted-foreground mb-4">
        Unable to connect to the server. Please check your internet connection
        and try again.
      </p>
      {onRetry && (
        <Button onClick={onRetry} className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Reconnect
        </Button>
      )}
    </div>
  )
}

// =============================================================================
// RATE LIMIT ERROR COMPONENT
// =============================================================================

interface RateLimitErrorProps {
  retryAfter?: number // seconds
  onRetry?: () => void
  className?: string
}

export const RateLimitError: React.FC<RateLimitErrorProps> = ({
  retryAfter = 60,
  onRetry,
  className = '',
}) => {
  const [countdown, setCountdown] = React.useState(retryAfter)

  React.useEffect(() => {
    if (countdown <= 0) return

    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1)
    }, 1000)

    return () => clearInterval(timer)
  }, [countdown])

  return (
    <div
      className={`flex flex-col items-center text-center p-6 ${className}`}
      role="alert"
      aria-live="polite"
    >
      <div className="h-16 w-16 rounded-full bg-orange-100 dark:bg-orange-900/20 flex items-center justify-center mb-4">
        <svg
          className="h-8 w-8 text-orange-600 dark:text-orange-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <h3 className="font-semibold text-lg mb-2">Too Many Requests</h3>
      <p className="text-sm text-muted-foreground mb-4">
        You&apos;ve sent too many messages. Please wait before trying again.
      </p>
      {countdown > 0 ? (
        <p className="text-2xl font-mono font-bold text-primary">
          {Math.floor(countdown / 60)}:{(countdown % 60).toString().padStart(2, '0')}
        </p>
      ) : (
        onRetry && (
          <Button onClick={onRetry} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Try Again
          </Button>
        )
      )}
    </div>
  )
}

export default ChatErrorBoundary
