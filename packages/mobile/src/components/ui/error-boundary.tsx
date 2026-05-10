/**
 * React Error Boundary with retry capability
 *
 * Catches rendering errors in the subtree and shows a friendly fallback UI
 * with a retry button. Accepts an optional custom fallback.
 */

import React from 'react';
import { View, StyleSheet } from 'react-native';
import { Text, Button } from 'react-native-paper';

import { spacing } from '@core/theme';
import i18n from '@core/i18n';
import { captureException } from '@core/observability/sentry';

// ---------------------------------------------------------------------------
// Props & State
// ---------------------------------------------------------------------------

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Custom fallback rendered instead of the default error UI. */
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

// ---------------------------------------------------------------------------
// Component (class-based — required by React error boundary API)
// ---------------------------------------------------------------------------

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  /**
   * Forward the captured error to Sentry. Without this, the parent
   * `SentryErrorBoundary` never sees the error because *this* boundary
   * intercepts it first via `getDerivedStateFromError`. The capture is a
   * no-op when Sentry is inactive (DEV / no DSN).
   */
  override componentDidCatch(error: Error, info: React.ErrorInfo): void {
    captureException(error, {
      tag: 'ErrorBoundary',
      extra: { componentStack: info.componentStack ?? '' },
    });
  }

  private resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  override render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <View style={styles.container}>
          <Text variant="headlineSmall" style={styles.title}>
            {i18n.t('common.error')}
          </Text>
          {this.state.error?.message && (
            <Text variant="bodyMedium" style={styles.description}>
              {this.state.error.message}
            </Text>
          )}
          <Button mode="contained" onPress={this.resetError} style={styles.button}>
            {i18n.t('common.retry')}
          </Button>
        </View>
      );
    }

    return this.props.children;
  }
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: spacing.lg,
  },
  title: {
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  description: {
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  button: {
    marginTop: spacing.sm,
  },
});
