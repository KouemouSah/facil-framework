/**
 * useAuth Hook - Facil Inspeccion
 */

import { useContext } from 'react';
import { AuthContext, type AuthContextValue } from '@core/auth/auth-provider';

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
