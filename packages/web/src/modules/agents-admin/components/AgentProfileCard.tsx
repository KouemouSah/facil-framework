'use client';

/**
 * Agent Profile Card Component
 * Displays agent profile information in a card format
 *
 * @module agents-admin/components
 */

import { useTranslations } from 'next-intl';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  User,
  Building2,
  Mail,
  Phone,
  Shield,
  MoreVertical,
  UserCheck,
  UserX,
  Edit,
  Trash2,
  BarChart3,
  Clock,
} from 'lucide-react';
import type { AgentProfile, AgentType, WorkloadStatus } from '../types';

interface AgentProfileCardProps {
  profile: AgentProfile;
  onEdit?: (profile: AgentProfile) => void;
  onDeactivate?: (profile: AgentProfile) => void;
  onReactivate?: (profile: AgentProfile) => void;
  onDelete?: (profile: AgentProfile) => void;
  onViewWorkload?: (profile: AgentProfile) => void;
  onViewPerformance?: (profile: AgentProfile) => void;
}

export function AgentProfileCard({
  profile,
  onEdit,
  onDeactivate,
  onReactivate,
  onDelete,
  onViewWorkload,
  onViewPerformance,
}: AgentProfileCardProps) {
  const t = useTranslations('admin.agents');

  const getInitials = (name?: string) => {
    if (!name) return 'AG';
    const parts = name.split(' ');
    return parts.length >= 2
      ? `${parts[0][0]}${parts[1][0]}`.toUpperCase()
      : name.substring(0, 2).toUpperCase();
  };

  const getAgentTypeBadge = (type: AgentType | string) => {
    const typeLabels: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
      ministry_agent: { label: t('card.ministry'), variant: 'default' },
      entity_agent: { label: t('card.entity'), variant: 'secondary' },
    };
    const config = typeLabels[type] || { label: type, variant: 'outline' as const };
    return <Badge variant={config.variant}>{config.label}</Badge>;
  };

  const getWorkloadStatusBadge = (status?: WorkloadStatus | string) => {
    if (!status) return null;

    const statusConfig: Record<string, { label: string; className: string }> = {
      available: { label: t('status.available'), className: 'bg-green-100 text-green-800' },
      normal: { label: t('status.normal'), className: 'bg-blue-100 text-blue-800' },
      busy: { label: t('status.busy'), className: 'bg-yellow-100 text-yellow-800' },
      overloaded: { label: t('status.overloaded'), className: 'bg-red-100 text-red-800' },
      unavailable: { label: t('status.unavailable'), className: 'bg-gray-100 text-gray-800' },
    };

    const config = statusConfig[status] || { label: status, className: 'bg-gray-100 text-gray-800' };
    return <Badge className={config.className}>{config.label}</Badge>;
  };

  const getStatusBadge = () => {
    if (profile.is_active) {
      return <Badge variant="default" className="bg-green-600">{t('card.active')}</Badge>;
    }
    return <Badge variant="destructive">{t('card.inactive')}</Badge>;
  };

  return (
    <Card className={`${!profile.is_active ? 'opacity-60' : ''}`}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Avatar className="h-12 w-12">
              <AvatarFallback className="bg-primary/10 text-primary">
                {getInitials(profile.user_full_name)}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle className="text-base font-medium">
                {profile.user_full_name || t('card.agent')}
              </CardTitle>
              <div className="flex items-center gap-2 mt-1">
                {getAgentTypeBadge(profile.agent_type)}
                {profile.is_supervisor && (
                  <Badge variant="outline" className="border-amber-500 text-amber-700">
                    <Shield className="h-3 w-3 mr-1" />
                    {t('card.supervisor')}
                  </Badge>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {getStatusBadge()}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onEdit && (
                  <DropdownMenuItem onClick={() => onEdit(profile)}>
                    <Edit className="h-4 w-4 mr-2" />
                    {t('card.modify')}
                  </DropdownMenuItem>
                )}
                {onViewWorkload && (
                  <DropdownMenuItem onClick={() => onViewWorkload(profile)}>
                    <BarChart3 className="h-4 w-4 mr-2" />
                    {t('card.workload')}
                  </DropdownMenuItem>
                )}
                {onViewPerformance && (
                  <DropdownMenuItem onClick={() => onViewPerformance(profile)}>
                    <Clock className="h-4 w-4 mr-2" />
                    {t('card.performance')}
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                {profile.is_active && onDeactivate && (
                  <DropdownMenuItem
                    onClick={() => onDeactivate(profile)}
                    className="text-orange-600"
                  >
                    <UserX className="h-4 w-4 mr-2" />
                    {t('card.deactivate')}
                  </DropdownMenuItem>
                )}
                {!profile.is_active && onReactivate && (
                  <DropdownMenuItem
                    onClick={() => onReactivate(profile)}
                    className="text-green-600"
                  >
                    <UserCheck className="h-4 w-4 mr-2" />
                    {t('card.reactivate')}
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => onDelete(profile)}
                      className="text-red-600"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      {t('card.delete')}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Contact Info */}
        <div className="space-y-1.5 text-sm">
          {profile.user_email && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Mail className="h-4 w-4" />
              <span className="truncate">{profile.user_email}</span>
            </div>
          )}
          {profile.user_phone && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="h-4 w-4" />
              <span>{profile.user_phone}</span>
            </div>
          )}
        </div>

        {/* Organization */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Building2 className="h-4 w-4" />
          <span>
            {profile.entity_name || profile.ministry_name || t('card.notAssigned')}
          </span>
        </div>

        {/* Role & Workload */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm capitalize">
              {profile.agent_type?.replace('_', ' ') || t('card.agent')}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getWorkloadStatusBadge(profile.workload_status)}
            {profile.current_assignments !== undefined && (
              <span className="text-xs text-muted-foreground">
                {t('card.tasks', { count: profile.current_assignments })}
              </span>
            )}
          </div>
        </div>

        {/* Specializations */}
        {profile.specializations && profile.specializations.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-2">
            {profile.specializations.slice(0, 3).map((spec) => (
              <Badge key={spec} variant="outline" className="text-xs">
                {spec}
              </Badge>
            ))}
            {profile.specializations.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{profile.specializations.length - 3}
              </Badge>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default AgentProfileCard;
