'use client';

/**
 * Page d'authentification dédiée aux agents
 * Design épuré et professionnel avec icône sécurité
 *
 * Route: /[locale]/auth/agent
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { Shield, Eye, EyeOff, Loader2 } from 'lucide-react';
import { authApi } from '@/core/api/auth';
import { setAuthData } from '@/core/auth/storage';
import { loginSchema } from '@/core/validations/auth';
import { z } from 'zod';
import { useLocale, useTranslations } from 'next-intl';

export default function AgentAuthPage() {
  const router = useRouter();
  const { toast } = useToast();
  const locale = useLocale();
  const t = useTranslations('auth');

  // État Login
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // État 2FA
  const [requires2FA, setRequires2FA] = useState(false);
  const [tempToken, setTempToken] = useState('');
  const [twoFactorCode, setTwoFactorCode] = useState('');

  // Handler Login
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrors({});
    setLoading(true);

    try {
      // Validation Zod
      const validated = loginSchema.parse({
        email,
        password,
        remember_me: true,
      });

      // Appel API
      const response = await authApi.login(validated);

      // Check if 2FA is required
      if ('requires_2fa' in response && response.requires_2fa) {
        setRequires2FA(true);
        setTempToken(response.temp_token);
        toast({
          title: t('twoFactorRequiredToast'),
          description: t('twoFactorRequiredMessage'),
        });
        return;
      }

      // Standard login (no 2FA)
      if ('access_token' in response) {
        // Verify this is an agent/admin/supervisor account
        const role = response.user.role?.toLowerCase() || '';
        if (role !== 'admin' && role !== 'agent' && !role.startsWith('agent_') && !role.startsWith('supervisor_')) {
          toast({
            variant: 'destructive',
            title: t('accessDenied'),
            description: t('agentOnlyPortal'),
          });
          setLoading(false);
          return;
        }

        setAuthData(response);

        toast({
          title: t('loginSuccess'),
          description: t('loginWelcome', { name: response.user.first_name || response.user.email }),
        });

        // Redirect based on role
        setTimeout(() => {
          const userRole = response.user.role?.toLowerCase() || '';
          if (userRole === 'admin') {
            router.push(`/${locale}/dashboard/admin`);
          } else if (userRole.startsWith('supervisor_')) {
            router.push(`/${locale}/dashboard/supervisor`);
          } else {
            router.push(`/${locale}/dashboard/agent`);
          }
        }, 500);
      }
    } catch (error: unknown) {
      if (error instanceof z.ZodError) {
        const fieldErrors: Record<string, string> = {};
        error.errors.forEach((err) => {
          if (err.path[0]) {
            fieldErrors[err.path[0].toString()] = err.message;
          }
        });
        setErrors(fieldErrors);
      } else {
        const errorMessage = error instanceof Error ? error.message : t('invalidCredentials');
        toast({
          variant: 'destructive',
          title: t('loginError'),
          description: errorMessage,
        });
      }
    } finally {
      setLoading(false);
    }
  };

  // Handler 2FA Verification
  const handle2FAVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (twoFactorCode.length !== 6) {
        toast({
          variant: 'destructive',
          title: t('invalidCode'),
          description: t('invalidCodeMessage'),
        });
        setLoading(false);
        return;
      }

      const response = await authApi.verify2FA({
        temp_token: tempToken,
        code: twoFactorCode,
      });

      setAuthData(response);

      toast({
        title: t('loginSuccess'),
        description: t('loginWelcome', { name: response.user.first_name || response.user.email }),
      });

      setTimeout(() => {
        const userRole = response.user.role?.toLowerCase() || '';
        if (userRole === 'admin') {
          router.push(`/${locale}/dashboard/admin`);
        } else if (userRole.startsWith('supervisor_')) {
          router.push(`/${locale}/dashboard/supervisor`);
        } else {
          router.push(`/${locale}/dashboard/agent`);
        }
      }, 500);
    } catch (error: unknown) {
      toast({
        variant: 'destructive',
        title: t('invalidTwoFactorCode'),
        description: error instanceof Error ? error.message : t('invalidTwoFactorMessage'),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-slate-100 to-slate-200 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-md">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <Link href={`/${locale}`} className="group">
              <Image
                src="/logo.png"
                alt="Facil"
                width={133} height={56}
                className="h-14 w-auto transition-transform group-hover:scale-105"
              />
            </Link>
          </div>

          {/* Auth Card */}
          <Card className="shadow-xl border-0 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm">
            <CardHeader className="text-center pb-2">
              <CardTitle className="text-2xl font-bold">{t('agentPortalTitle')}</CardTitle>
              <CardDescription className="text-base">
                {t('agentPortalDescription')}
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-4">
              {!requires2FA ? (
                // Login Form
                <form onSubmit={handleLogin} className="space-y-5">
                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-sm font-medium">
                      {t('email')}
                    </Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="agent@facil.gq"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      disabled={loading}
                      className="h-11"
                    />
                    {errors.email && (
                      <p className="text-sm text-destructive">{errors.email}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="password" className="text-sm font-medium">
                      {t('password')}
                    </Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={loading}
                        className="h-11 pr-10"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                        tabIndex={-1}
                      >
                        {showPassword ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                    {errors.password && (
                      <p className="text-sm text-destructive">{errors.password}</p>
                    )}
                  </div>

                  <Button
                    type="submit"
                    className="w-full h-11 text-base font-semibold"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {t('loginButtonLoading')}
                      </>
                    ) : (
                      <>
                        <Shield className="mr-2 h-4 w-4" />
                        {t('loginButton')}
                      </>
                    )}
                  </Button>

                  <div className="text-center pt-2">
                    <Link
                      href={`/${locale}/auth/forgot-password`}
                      className="text-sm text-primary hover:underline"
                    >
                      {t('forgotPasswordLink')}
                    </Link>
                  </div>
                </form>
              ) : (
                // 2FA Form
                <form onSubmit={handle2FAVerify} className="space-y-5">
                  <div className="text-center mb-4">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 mb-3">
                      <Shield className="h-8 w-8 text-primary" />
                    </div>
                    <h3 className="text-lg font-semibold mb-1">{t('twoFactorRequired')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('twoFactorDescription')}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="2fa-code">{t('verificationCodeLabel')}</Label>
                    <Input
                      id="2fa-code"
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="000000"
                      value={twoFactorCode}
                      onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, ''))}
                      className="text-center text-2xl tracking-[0.5em] h-14 font-mono"
                      required
                      autoFocus
                    />
                  </div>

                  <Button type="submit" className="w-full h-11" disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        {t('verifyButtonLoading')}
                      </>
                    ) : (
                      t('verifyButton')
                    )}
                  </Button>

                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      setRequires2FA(false);
                      setTempToken('');
                      setTwoFactorCode('');
                    }}
                  >
                    {t('backButton')}
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          {/* Info Text */}
          <p className="text-center text-sm text-muted-foreground mt-6">
            {t('notAnAgent')}{' '}
            <Link href={`/${locale}/auth`} className="text-primary hover:underline font-medium">
              {t('standardLogin')}
            </Link>
          </p>
        </div>
      </main>

      {/* Footer Minimaliste - Sans bouton aide */}
      <footer className="py-4 border-t bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-center text-sm text-muted-foreground">
            <span>&copy; {new Date().getFullYear()} Facil - Plataforma Digital AI de Tramites</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
