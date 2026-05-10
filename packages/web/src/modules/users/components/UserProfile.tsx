'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { User, Mail, Phone, MapPin, Calendar, Shield } from 'lucide-react';
import { formatDate } from '@/core/utils';

interface UserData {
  id: string;
  email: string;
  role: string;
  status: string;
  first_name: string;
  last_name: string;
  phone?: string;
  address?: string;
  city?: string;
  created_at: string;
  email_verified?: boolean;
  two_factor_enabled?: boolean;
}

interface UserProfileProps {
  user: UserData;
  onEdit?: () => void;
}

export const UserProfile = ({ user, onEdit }: UserProfileProps) => {
  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      admin: 'bg-red-500',
      dgi_agent: 'bg-blue-500',
      accountant: 'bg-purple-500',
      business: 'bg-green-500',
      citizen: 'bg-gray-500',
    };
    return colors[role] || 'bg-gray-500';
  };

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="h-8 w-8 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-bold">
              {user.first_name} {user.last_name}
            </h2>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        </div>
        <Badge className={getRoleBadge(user.role)}>{user.role}</Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm">
            <Mail className="h-4 w-4 text-muted-foreground" />
            <span>{user.email}</span>
            {user.email_verified && (
              <Badge variant="outline" className="text-xs">
                Vérifié
              </Badge>
            )}
          </div>

          {user.phone && (
            <div className="flex items-center gap-2 text-sm">
              <Phone className="h-4 w-4 text-muted-foreground" />
              <span>{user.phone}</span>
            </div>
          )}

          {(user.address || user.city) && (
            <div className="flex items-center gap-2 text-sm">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span>
                {user.address}
                {user.city && `, ${user.city}`}
              </span>
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <span>Membre depuis {formatDate(user.created_at)}</span>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <span>2FA: {user.two_factor_enabled ? 'Activé' : 'Désactivé'}</span>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Statut:</span>
            <Badge
              variant={user.status === 'active' ? 'default' : 'secondary'}
            >
              {user.status}
            </Badge>
          </div>
        </div>
      </div>

      {onEdit && (
        <div className="mt-6 pt-6 border-t">
          <Button onClick={onEdit} className="w-full">
            Modifier le profil
          </Button>
        </div>
      )}
    </Card>
  );
};

export default UserProfile;
