'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { loginSchema, type LoginInput } from '@/core/validations/auth';
import { authApi, type TokenResponse } from '@/core/api/auth';
import { setAuthData } from '@/core/auth/storage';
import { AlertCircle, Loader2 } from 'lucide-react';
import { usePrefetchMenuConfig } from '@/modules/agent-dashboard/hooks/useMenuConfig';

export const LoginForm = () => {
  const router = useRouter();
  const locale = useLocale();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { prefetch: prefetchMenuConfig } = usePrefetchMenuConfig();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginInput) => {
    try {
      setLoading(true);
      setError(null);

      const response = await authApi.login(data);

      // Check if 2FA required
      if ('requires_2fa' in response && response.requires_2fa) {
        // Store temp token in sessionStorage (never in URL — prevents server logs/referer leaks)
        sessionStorage.setItem('2fa_temp_token', response.temp_token);
        router.push(`/${locale}/auth/2fa-verify`);
        return;
      }

      // Store auth data
      const tokenResponse = response as TokenResponse;
      setAuthData(tokenResponse);

      // Prefetch menu config for agents (non-blocking)
      if (tokenResponse.user?.role === 'agent' && tokenResponse.user?.id) {
        prefetchMenuConfig(tokenResponse.user.id).catch(() => {
          // Ignore prefetch errors - they're non-critical
        });
      }

      // Redirect to dashboard
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Échec de la connexion');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="p-6 max-w-md w-full">
      <div className="mb-6 text-center">
        <h2 className="text-2xl font-bold">Connexion</h2>
        <p className="text-muted-foreground mt-2">Connectez-vous à votre compte Facil</p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="vous@example.com"
            {...register('email')}
            disabled={loading}
          />
          {errors.email && (
            <p className="text-sm text-destructive">{errors.email.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Mot de passe</Label>
          <Input
            id="password"
            type="password"
            placeholder="••••••••"
            {...register('password')}
            disabled={loading}
          />
          {errors.password && (
            <p className="text-sm text-destructive">{errors.password.message}</p>
          )}
        </div>

        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2">
            <input type="checkbox" {...register('remember_me')} disabled={loading} />
            <span className="text-sm">Se souvenir de moi</span>
          </label>
          <a href="/auth/forgot-password" className="text-sm text-primary hover:underline">
            Mot de passe oublié?
          </a>
        </div>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Connexion...
            </>
          ) : (
            'Se connecter'
          )}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Pas encore de compte?{' '}
        <a href="/auth/register" className="text-primary hover:underline">
          S&apos;inscrire
        </a>
      </p>
    </Card>
  );
};

export default LoginForm;
