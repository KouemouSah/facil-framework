/**
 * DashboardErrorBoundary Component
 * Error boundary for graceful error handling in dashboard components
 *
 * @module components/layout
 * @date 2026-01-18
 *
 * Features:
 * - Catches JavaScript errors in child components
 * - Displays user-friendly error message
 * - Retry mechanism
 * - Error logging
 */

'use client'

import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertCircle, RefreshCw, Home } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

// =============================================================================
// TYPES
// =============================================================================

interface DashboardErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface DashboardErrorBoundaryState {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

// =============================================================================
// ERROR BOUNDARY CLASS COMPONENT
// =============================================================================

export class DashboardErrorBoundary extends Component<
  DashboardErrorBoundaryProps,
  DashboardErrorBoundaryState
> {
  constructor(props: DashboardErrorBoundaryProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<DashboardErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error to console
    console.error('DashboardErrorBoundary caught an error:', error, errorInfo)

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
  }

  handleGoHome = (): void => {
    // Navigate to the dashboard section the user was in (admin, agent, supervisor, etc.)
    if (typeof window !== 'undefined') {
      const pathParts = window.location.pathname.split('/')
      const locale = pathParts[1] && ['es', 'fr', 'en'].includes(pathParts[1]) ? pathParts[1] : 'es'
      // pathParts: ['', locale, 'dashboard', section?, ...]
      // If user was in /es/dashboard/admin/..., go back to /es/dashboard/admin
      const section = pathParts[3] || ''
      const dashboardSections = ['admin', 'agent', 'supervisor', 'treasury']
      if (section && dashboardSections.includes(section)) {
        window.location.href = `/${locale}/dashboard/${section}`
      } else {
        window.location.href = `/${locale}/dashboard`
      }
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
        <div className="flex items-center justify-center min-h-[400px] p-4">
          <Card className="max-w-md w-full border-destructive/50 bg-destructive/5">
            <CardContent className="p-6">
              <div className="flex flex-col items-center text-center space-y-4">
                <div className="h-12 w-12 rounded-full bg-destructive/10 flex items-center justify-center">
                  <AlertCircle className="h-6 w-6 text-destructive" />
                </div>

                <div className="space-y-2">
                  <h3 className="font-semibold text-lg text-destructive">
                    Error de carga
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Ha ocurrido un error al cargar esta pagina. Por favor intente nuevamente.
                  </p>
                </div>

                {/* Error details in development */}
                {process.env.NODE_ENV === 'development' && this.state.error && (
                  <details className="w-full text-left">
                    <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
                      Detalles tecnicos
                    </summary>
                    <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto whitespace-pre-wrap">
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
                    Reintentar
                  </Button>
                  <Button
                    variant="outline"
                    onClick={this.handleGoHome}
                    className="gap-2"
                  >
                    <Home className="h-4 w-4" />
                    Inicio
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )
    }

    return this.props.children
  }
}

export default DashboardErrorBoundary
