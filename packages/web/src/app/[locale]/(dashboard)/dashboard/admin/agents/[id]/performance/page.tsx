'use client';

/**
 * Agent Performance Detail Page
 * Detailed view of agent performance metrics and statistics
 *
 * @module dashboard/admin/agents/[id]/performance
 * @date 2025-01-14
 */

import { useRouter, useParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  ArrowLeft,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Target,
  Award,
  Calendar,
  Activity,
} from 'lucide-react';
import {
  useAgentProfile,
  useAgentPerformance,
  useAgentWorkload,
} from '@/modules/agents-admin/hooks';
import { PerformanceStats } from '@/modules/agents-admin/components';

// =============================================================================
// COMPONENT
// =============================================================================

export default function AgentPerformancePage() {
  const router = useRouter();
  const params = useParams();

  const profileId = params.id as string;

  // Queries
  const { data: profile, isLoading: profileLoading } = useAgentProfile(profileId);
  const { data: performance, isLoading: performanceLoading } = useAgentPerformance(profileId, !!profile);
  const { data: workload } = useAgentWorkload(profileId, !!profile);

  // Loading state
  if (profileLoading || performanceLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  // Error state
  if (!profile) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">Agent non trouvé</h1>
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              Le profil agent demandé n&apos;existe pas.
            </p>
            <Button className="mt-4" onClick={() => router.push('/dashboard/admin/agents')}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Calculate derived metrics
  const totalProcessed = performance?.current_month_processed || 0;
  const approvalRate = totalProcessed > 0
    ? ((performance?.current_month_approved || 0) / totalProcessed) * 100
    : 0;
  const rejectionRate = totalProcessed > 0
    ? ((performance?.current_month_rejected || 0) / totalProcessed) * 100
    : 0;
  const escalationRate = totalProcessed > 0
    ? ((performance?.current_month_escalated || 0) / totalProcessed) * 100
    : 0;

  const slaTotal = (performance?.sla_respected_count || 0) + (performance?.sla_missed_count || 0);
  const slaRate = slaTotal > 0
    ? ((performance?.sla_respected_count || 0) / slaTotal) * 100
    : 100;

  // Calculate performance score (weighted average)
  const performanceScore = Math.round(
    (approvalRate * 0.3) +
    ((100 - escalationRate) * 0.2) +
    (slaRate * 0.3) +
    ((workload?.quality_score_avg || 80) * 0.2)
  );

  const getScoreBadge = (score: number) => {
    if (score >= 90) return { variant: 'default' as const, label: 'Excellent', color: 'bg-green-500' };
    if (score >= 75) return { variant: 'secondary' as const, label: 'Bon', color: 'bg-blue-500' };
    if (score >= 60) return { variant: 'outline' as const, label: 'Acceptable', color: 'bg-yellow-500' };
    return { variant: 'destructive' as const, label: 'À améliorer', color: 'bg-red-500' };
  };

  const scoreBadge = getScoreBadge(performanceScore);

  const formatDuration = (minutes?: number) => {
    if (!minutes) return '-';
    if (minutes < 60) return `${Math.round(minutes)} min`;
    if (minutes < 1440) return `${(minutes / 60).toFixed(1)}h`;
    return `${(minutes / 1440).toFixed(1)}j`;
  };

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
              <BarChart3 className="h-8 w-8" />
              Performance
            </h1>
            <p className="text-muted-foreground mt-1">
              {profile.user_full_name} - {profile.ministry_name || profile.entity_name}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <Badge variant={scoreBadge.variant} className="text-lg px-4 py-2">
            Score: {performanceScore}/100 - {scoreBadge.label}
          </Badge>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Total Traité
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{totalProcessed}</p>
            <p className="text-xs text-muted-foreground">ce mois</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              Approuvés
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-green-600">{performance?.current_month_approved || 0}</p>
            <p className="text-xs text-muted-foreground">{approvalRate.toFixed(1)}%</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              Rejetés
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-red-600">{performance?.current_month_rejected || 0}</p>
            <p className="text-xs text-muted-foreground">{rejectionRate.toFixed(1)}%</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-orange-500" />
              Escaladés
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-orange-600">{performance?.current_month_escalated || 0}</p>
            <p className="text-xs text-muted-foreground">{escalationRate.toFixed(1)}%</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Target className="h-4 w-4 text-blue-500" />
              Respect SLA
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-blue-600">{slaRate.toFixed(0)}%</p>
            <p className="text-xs text-muted-foreground">
              {performance?.sla_respected_count || 0}/{slaTotal}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Performance Display */}
      {performance && <PerformanceStats performance={performance} />}

      {/* Additional Metrics */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Processing Efficiency */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Efficacité de traitement
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Temps moyen de traitement</span>
                <span className="font-medium">{formatDuration(performance?.avg_processing_minutes)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Durée moyenne de verrouillage</span>
                <span className="font-medium">{formatDuration(performance?.avg_lock_duration_minutes)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Verrouillages actifs</span>
                <span className="font-medium">{performance?.current_active_locks || 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Max verrouillages simultanés</span>
                <span className="font-medium">{performance?.max_concurrent_locks || 0}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Quality Metrics from Workload */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="h-5 w-5" />
              Qualité et fiabilité
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-muted-foreground">Score qualité</span>
                  <span className="font-medium">{(workload?.quality_score_avg || 0).toFixed(1)}%</span>
                </div>
                <Progress value={workload?.quality_score_avg || 0} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-muted-foreground">Taux de succès</span>
                  <span className="font-medium">{(workload?.success_rate || 0).toFixed(1)}%</span>
                </div>
                <Progress value={workload?.success_rate || 0} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-muted-foreground">Respect des délais</span>
                  <span className="font-medium">{(workload?.deadline_compliance_rate || 0).toFixed(1)}%</span>
                </div>
                <Progress value={workload?.deadline_compliance_rate || 0} className="h-2" />
              </div>
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm text-muted-foreground">Taux de complétion (7j)</span>
                  <span className="font-medium">{(workload?.completion_rate_7d || 0).toFixed(1)}%</span>
                </div>
                <Progress value={workload?.completion_rate_7d || 0} className="h-2" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Activité récente
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <p className="text-sm text-muted-foreground">Dernière action</p>
              <p className="font-medium">
                {performance?.last_action_at
                  ? new Date(performance.last_action_at).toLocaleString()
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Dernière connexion</p>
              <p className="font-medium">
                {performance?.last_login_at
                  ? new Date(performance.last_login_at).toLocaleString()
                  : '-'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Début de période</p>
              <p className="font-medium">
                {performance?.stats_period_start || '-'}
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Fin de période</p>
              <p className="font-medium">
                {performance?.stats_period_end || 'En cours'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance Insights */}
      <Card>
        <CardHeader>
          <CardTitle>Analyse et recommandations</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* SLA Analysis */}
            {slaRate < 80 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-red-50 border border-red-200">
                <TrendingDown className="h-5 w-5 text-red-500 mt-0.5" />
                <div>
                  <p className="font-medium text-red-800">Respect SLA insuffisant</p>
                  <p className="text-sm text-red-700">
                    Le taux de respect des SLA est de {slaRate.toFixed(0)}%.
                    Considérez réduire le nombre d&apos;assignations simultanées ou
                    revoir la priorisation des dossiers.
                  </p>
                </div>
              </div>
            )}

            {/* Escalation Analysis */}
            {escalationRate > 20 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-orange-50 border border-orange-200">
                <AlertTriangle className="h-5 w-5 text-orange-500 mt-0.5" />
                <div>
                  <p className="font-medium text-orange-800">Taux d&apos;escalade élevé</p>
                  <p className="text-sm text-orange-700">
                    {escalationRate.toFixed(0)}% des dossiers sont escaladés.
                    Une formation complémentaire pourrait aider à réduire ce taux.
                  </p>
                </div>
              </div>
            )}

            {/* Positive feedback */}
            {performanceScore >= 80 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-green-50 border border-green-200">
                <TrendingUp className="h-5 w-5 text-green-500 mt-0.5" />
                <div>
                  <p className="font-medium text-green-800">Excellente performance</p>
                  <p className="text-sm text-green-700">
                    L&apos;agent maintient un score de performance de {performanceScore}/100.
                    Continuez ainsi!
                  </p>
                </div>
              </div>
            )}

            {/* Workload recommendation */}
            {(workload?.capacity_percentage || 0) > 90 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-yellow-50 border border-yellow-200">
                <Activity className="h-5 w-5 text-yellow-500 mt-0.5" />
                <div>
                  <p className="font-medium text-yellow-800">Capacité proche du maximum</p>
                  <p className="text-sm text-yellow-700">
                    L&apos;agent est à {workload?.capacity_percentage}% de sa capacité.
                    Évitez d&apos;assigner de nouveaux dossiers complexes.
                  </p>
                </div>
              </div>
            )}

            {/* No issues */}
            {performanceScore >= 60 && slaRate >= 80 && escalationRate <= 20 && (workload?.capacity_percentage || 0) <= 90 && (
              <div className="flex items-start gap-3 p-3 rounded-lg bg-blue-50 border border-blue-200">
                <CheckCircle2 className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-800">Tout est en ordre</p>
                  <p className="text-sm text-blue-700">
                    Les métriques de performance sont dans les normes attendues.
                  </p>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
