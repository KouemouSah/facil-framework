'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { registerSchema, type RegisterInput } from '@/core/validations/auth';
import { authApi } from '@/core/api/auth';
import { setAuthData } from '@/core/auth/storage';
import { AlertCircle, Loader2, CheckCircle } from 'lucide-react';

export const RegisterForm = () => {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'request-code' | 'register'>('request-code');
  const [email, setEmail] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      role: 'citizen',
    },
  });

  const handleRequestCode = async () => {
    try {
      setLoading(true);
      setError(null);
      await authApi.requestVerificationCode(email);
      setStep('register');
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'envoi du code");
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (data: RegisterInput) => {
    try {
      setLoading(true);
      setError(null);

      const response = await authApi.register({ ...data, email });
      setAuthData(response);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'inscription");
    } finally {
      setLoading(false);
    }
  };

  if (step === 'request-code') {
    return (
      <Card className="p-6 max-w-md w-full">
        <div className="mb-6 text-center">
          <h2 className="text-2xl font-bold">Inscription</h2>
          <p className="text-muted-foreground mt-2">
            Étape 1: Demander un code de vérification
          </p>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="vous@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
            />
          </div>

          <Button onClick={handleRequestCode} className="w-full" disabled={loading || !email}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Envoi...
              </>
            ) : (
              'Recevoir le code de vérification'
            )}
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 max-w-md w-full">
      <div className="mb-6 text-center">
        <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-3" />
        <h2 className="text-2xl font-bold">Inscription</h2>
        <p className="text-muted-foreground mt-2">
          Étape 2: Complétez votre inscription
        </p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="verification_code">Code de vérification</Label>
          <Input
            id="verification_code"
            type="text"
            placeholder="123456"
            {...register('verification_code')}
            disabled={loading}
          />
          {errors.verification_code && (
            <p className="text-sm text-destructive">{errors.verification_code.message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="first_name">Prénom</Label>
            <Input
              id="first_name"
              type="text"
              placeholder="Jean"
              {...register('first_name')}
              disabled={loading}
            />
            {errors.first_name && (
              <p className="text-sm text-destructive">{errors.first_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="last_name">Nom</Label>
            <Input
              id="last_name"
              type="text"
              placeholder="Dupont"
              {...register('last_name')}
              disabled={loading}
            />
            {errors.last_name && (
              <p className="text-sm text-destructive">{errors.last_name.message}</p>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="phone">Téléphone</Label>
          <Input
            id="phone"
            type="tel"
            placeholder="222123456"
            {...register('phone')}
            disabled={loading}
          />
          {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
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

        <div className="space-y-2">
          <Label htmlFor="role">Type de compte</Label>
          <select
            id="role"
            {...register('role')}
            disabled={loading}
            className="w-full border rounded-md p-2"
          >
            <option value="citizen">Citoyen</option>
            <option value="business">Entreprise</option>
          </select>
          {errors.role && <p className="text-sm text-destructive">{errors.role.message}</p>}
        </div>

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Inscription...
            </>
          ) : (
            "S'inscrire"
          )}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Déjà un compte?{' '}
        <a href="/auth/login" className="text-primary hover:underline">
          Se connecter
        </a>
      </p>
    </Card>
  );
};

export default RegisterForm;
