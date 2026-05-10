'use client';

/**
 * User Detail Page - Read Only
 * Display user details without modification capabilities
 *
 * BUSINESS RULES:
 * - Read-only view of user information
 * - No edit capabilities (users manage their own profiles)
 * - Only Activate/Deactivate actions available
 * - Shows: profile info, account status, activity
 *
 * @module dashboard/admin/users/[id]
 * @date 2025-01-14
 */

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useLocale, useTranslations } from 'next-intl';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  ArrowLeft,
  User as UserIcon,
  Mail,
  Phone,
  MapPin,
  Globe,
  Calendar,
  Clock,
  Shield,
  Power,
  PowerOff,
  Building2,
  Briefcase,
  UserCheck,
  RefreshCw,
  AlertTriangle,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import usersApi from '@/modules/users-admin/services/api';
import type { User as UserType } from '@/modules/users-admin/types';
import { UserRole } from '@/types/user';
import { useUserLabels } from '@/hooks/use-user-labels';

export default function UserDetailPage() {
  const router = useRouter();
  const params = useParams();
  const locale = useLocale();
  const t = useTranslations('admin.users');
  const { toast } = useToast();
  const { getRoleLabel } = useUserLabels();

  const userId = params.id as string;

  const [user, setUser] = useState<UserType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialog states
  const [activateDialogOpen, setActivateDialogOpen] = useState(false);
  const [deactivateDialogOpen, setDeactivateDialogOpen] = useState(false);
  const [deactivateReason, setDeactivateReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Fetch user
  const fetchUser = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await usersApi.getById(userId);
      setUser(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors du chargement';
      setError(errorMessage);
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: errorMessage,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (userId) {
      fetchUser();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  const handleActivate = async () => {
    if (!user) return;

    setIsProcessing(true);
    try {
      await usersApi.setActive(user.id, true);
      toast({
        title: t('successTitle'),
        description: t('userActivated'),
      });
      fetchUser();
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorActivating'),
      });
    } finally {
      setIsProcessing(false);
      setActivateDialogOpen(false);
    }
  };

  const handleDeactivate = async () => {
    if (!user) return;

    setIsProcessing(true);
    try {
      await usersApi.setActive(user.id, false);
      toast({
        title: t('successTitle'),
        description: t('userDeactivated'),
      });
      fetchUser();
    } catch (err) {
      toast({
        variant: 'destructive',
        title: t('errorTitle'),
        description: t('errorDeactivating'),
      });
    } finally {
      setIsProcessing(false);
      setDeactivateDialogOpen(false);
      setDeactivateReason('');
    }
  };

  const getRoleIcon = (role: UserRole) => {
    const icons: Record<string, React.ReactNode> = {
      citizen: <UserIcon className="h-5 w-5" />,
      business: <Building2 className="h-5 w-5" />,
      accountant: <Briefcase className="h-5 w-5" />,
      funcionario: <UserCheck className="h-5 w-5" />,
    };
    return icons[role] || <UserIcon className="h-5 w-5" />;
  };

  const getRoleBadgeColor = (role: UserRole) => {
    const colors: Record<string, string> = {
      citizen: 'bg-gray-100 text-gray-700',
      business: 'bg-green-100 text-green-700',
      accountant: 'bg-blue-100 text-blue-700',
      funcionario: 'bg-amber-100 text-amber-700',
    };
    return colors[role] || 'bg-gray-100 text-gray-700';
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString(locale, {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-4 w-48" />
          </div>
        </div>
        <Skeleton className="h-[300px] w-full" />
        <Skeleton className="h-[200px] w-full" />
      </div>
    );
  }

  // Error state
  if (error || !user) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Utilisateur non trouvé</h1>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-red-500 mb-4">
              <AlertTriangle className="h-5 w-5" />
              <p>{error || "L'utilisateur demandé n'existe pas."}</p>
            </div>
            <Button onClick={() => router.push('/dashboard/admin/users')}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
              {getRoleIcon(user.role)}
              {user.first_name} {user.last_name}
            </h1>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant={user.is_active ? 'default' : 'secondary'}>
                {user.is_active ? t('statusActive') : t('statusInactive')}
              </Badge>
              <Badge variant="outline" className={getRoleBadgeColor(user.role)}>
                {getRoleLabel(user.role)}
              </Badge>
              {user.two_factor_enabled && (
                <Badge variant="outline" className="bg-blue-100 text-blue-700">
                  <Shield className="h-3 w-3 mr-1" />
                  2FA activé
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {user.is_active ? (
            <Button
              variant="outline"
              className="text-red-600"
              onClick={() => setDeactivateDialogOpen(true)}
            >
              <PowerOff className="h-4 w-4 mr-2" />
              Désactiver
            </Button>
          ) : (
            <Button
              variant="outline"
              className="text-green-600"
              onClick={() => setActivateDialogOpen(true)}
            >
              <Power className="h-4 w-4 mr-2" />
              Activer
            </Button>
          )}
        </div>
      </div>

      {/* Read-Only Notice */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="pt-4 pb-4">
          <p className="text-sm text-blue-700">
            <strong>Vue en lecture seule.</strong> Les utilisateurs gèrent leur propre profil.
            Seules les actions d&apos;activation/désactivation sont disponibles.
          </p>
        </CardContent>
      </Card>

      {/* Profile Information */}
      <Card>
        <CardHeader>
          <CardTitle>Informations du profil</CardTitle>
          <CardDescription>
            Données personnelles de l&apos;utilisateur
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Contact Info */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex items-start gap-3">
              <Mail className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Email</p>
                <p className="font-medium">{user.email}</p>
                {user.email_verified ? (
                  <Badge variant="outline" className="mt-1 text-green-600">
                    Vérifié
                  </Badge>
                ) : (
                  <Badge variant="outline" className="mt-1 text-orange-600">
                    Non vérifié
                  </Badge>
                )}
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Phone className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Téléphone</p>
                <p className="font-medium">{user.phone_number || '-'}</p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Location */}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="flex items-start gap-3">
              <MapPin className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Adresse</p>
                <p className="font-medium">{user.address || '-'}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <MapPin className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Ville</p>
                <p className="font-medium">{user.city || '-'}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Globe className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Pays</p>
                <p className="font-medium">{user.country || 'Guinée Équatoriale'}</p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Preferences */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex items-start gap-3">
              <Globe className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Langue préférée</p>
                <p className="font-medium">
                  {user.preferred_language === 'es' && 'Español'}
                  {user.preferred_language === 'fr' && 'Français'}
                  {user.preferred_language === 'en' && 'English'}
                  {!user.preferred_language && 'Español (par défaut)'}
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Shield className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Authentification 2FA</p>
                <p className="font-medium">
                  {user.two_factor_enabled ? 'Activée' : 'Désactivée'}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Account Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Activité du compte</CardTitle>
          <CardDescription>
            Historique de connexion et création du compte
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-start gap-3">
              <Calendar className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Compte créé le</p>
                <p className="font-medium">{formatDate(user.created_at)}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Clock className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Dernière mise à jour</p>
                <p className="font-medium">{formatDate(user.updated_at)}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <UserIcon className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Dernière connexion</p>
                <p className="font-medium">{formatDate(user.last_login)}</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Mail className="h-5 w-5 text-muted-foreground mt-0.5" />
              <div>
                <p className="text-sm text-muted-foreground">Email vérifié le</p>
                <p className="font-medium">{formatDate(user.email_verified_at)}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Deactivation Info (if inactive) */}
      {!user.is_active && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-800 flex items-center gap-2">
              <PowerOff className="h-5 w-5" />
              Compte désactivé
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-700">
              Ce compte est actuellement désactivé. L&apos;utilisateur ne peut pas se connecter
              ni accéder aux services de la plateforme.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Activate Dialog */}
      <AlertDialog open={activateDialogOpen} onOpenChange={setActivateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Activer l&apos;utilisateur ?</AlertDialogTitle>
            <AlertDialogDescription>
              L&apos;utilisateur <strong>{user.first_name} {user.last_name}</strong> ({user.email})
              pourra à nouveau accéder à son compte.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isProcessing}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleActivate}
              disabled={isProcessing}
              className="bg-green-600 hover:bg-green-700"
            >
              {isProcessing ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Power className="h-4 w-4 mr-2" />
              )}
              Activer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Deactivate Dialog */}
      <AlertDialog open={deactivateDialogOpen} onOpenChange={setDeactivateDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver l&apos;utilisateur ?</AlertDialogTitle>
            <AlertDialogDescription>
              L&apos;utilisateur <strong>{user.first_name} {user.last_name}</strong> ({user.email})
              ne pourra plus accéder à son compte. Cette action est réversible.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Input
              placeholder="Raison de la désactivation (optionnel)"
              value={deactivateReason}
              onChange={(e) => setDeactivateReason(e.target.value)}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isProcessing}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeactivate}
              disabled={isProcessing}
              className="bg-red-600 hover:bg-red-700"
            >
              {isProcessing ? (
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <PowerOff className="h-4 w-4 mr-2" />
              )}
              Désactiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
