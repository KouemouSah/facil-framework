/**
 * useAuth Hook
 *
 * Convenience hook to consume the AuthContext.
 *
 * Throws a descriptive error if used outside of AuthProvider,
 * which helps catch layout configuration mistakes early.
 *
 * Usage:
 * ```tsx
 * const { user, isAuthenticated, signIn, signOut } = useAuth();
 * ```
 */

import { useContext } from 'react';

import { AuthContext } from '@core/auth/auth-provider';

/**
 * Access the auth context (user, auth state, and auth actions).
 *
 * @throws Error if called outside of <AuthProvider>
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      'useAuth must be used within an <AuthProvider>. ' +
      'Wrap your root layout with <AuthProvider> in app/_layout.tsx.',
    );
  }

  return context;
}
