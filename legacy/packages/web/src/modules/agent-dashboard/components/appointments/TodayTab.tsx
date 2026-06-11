/**
 * TodayTab Component
 * Displays today's appointments with actions
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-26
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
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
  Clock,
  User,
  Phone,
  Mail,
  CheckCircle2,
  XCircle,
  Eye,
  CalendarCheck,
  CalendarX,
  FileText,
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import {
  useTodayAppointments,
  useCompleteAppointment,
  useCancelAppointment,
  TodayAppointmentDetail,
} from '../../hooks/useAppointments';
import { AppointmentPreviewSheet } from './AppointmentPreviewSheet';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface TodayTabProps {
  entityCode: EntityCode;
  locationId?: string;
}

// =============================================================================
// STATUS STYLES
// =============================================================================

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  confirmed: { bg: 'bg-blue-100', text: 'text-blue-800', label: 'Confirmé' },
  pending: { bg: 'bg-yellow-100', text: 'text-yellow-800', label: 'En attente' },
  completed: { bg: 'bg-green-100', text: 'text-green-800', label: 'Terminé' },
  cancelled: { bg: 'bg-red-100', text: 'text-red-800', label: 'Annulé' },
  no_show: { bg: 'bg-gray-100', text: 'text-gray-800', label: 'Absent' },
};

// =============================================================================
// COMPONENT
// =============================================================================

export function TodayTab({ entityCode, locationId }: TodayTabProps) {
  const { toast } = useToast();
  const [selectedAppointment, setSelectedAppointment] = useState<TodayAppointmentDetail | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [appointmentToCancel, setAppointmentToCancel] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useTodayAppointments(entityCode, {
    locationId,
  });

  const completeMutation = useCompleteAppointment();
  const cancelMutation = useCancelAppointment();

  const handleView = (appointment: TodayAppointmentDetail) => {
    setSelectedAppointment(appointment);
    setPreviewOpen(true);
  };

  const handleComplete = async (appointmentId: string) => {
    try {
      await completeMutation.mutateAsync(appointmentId);
      toast({
        title: 'Rendez-vous terminé',
        description: 'Le rendez-vous a été marqué comme terminé.',
      });
      refetch();
    } catch (error) {
      toast({
        title: 'Erreur',
        description: error instanceof Error ? error.message : 'Impossible de terminer le rendez-vous',
        variant: 'destructive',
      });
    }
  };

  const handleCancelClick = (appointmentId: string) => {
    setAppointmentToCancel(appointmentId);
    setCancelDialogOpen(true);
  };

  const handleCancelConfirm = async () => {
    if (!appointmentToCancel) return;

    try {
      await cancelMutation.mutateAsync({
        reservationId: appointmentToCancel,
        reason: 'Annulé par agent',
      });
      toast({
        title: 'Rendez-vous annulé',
        description: 'Le rendez-vous a été annulé avec succès.',
      });
      refetch();
    } catch (error) {
      toast({
        title: 'Erreur',
        description: error instanceof Error ? error.message : 'Impossible d\'annuler le rendez-vous',
        variant: 'destructive',
      });
    } finally {
      setCancelDialogOpen(false);
      setAppointmentToCancel(null);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4 mb-4">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-24" />
        </div>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 w-full" />
        ))}
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <Card>
        <CardContent className="py-8 text-center">
          <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <p className="text-muted-foreground">
            Erreur lors du chargement des rendez-vous
          </p>
          <Button variant="outline" onClick={() => refetch()} className="mt-4">
            Réessayer
          </Button>
        </CardContent>
      </Card>
    );
  }

  const appointments = data?.appointments || [];
  const stats = {
    total: data?.total || 0,
    pending: data?.pending || 0,
    completed: data?.completed || 0,
    cancelled: data?.cancelled || 0,
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">Total RDV</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-blue-600">{stats.pending}</div>
            <p className="text-xs text-muted-foreground">En attente</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
            <p className="text-xs text-muted-foreground">Terminés</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-red-600">{stats.cancelled}</div>
            <p className="text-xs text-muted-foreground">Annulés</p>
          </CardContent>
        </Card>
      </div>

      {/* Appointments List */}
      {appointments.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <CalendarCheck className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-lg font-medium">Aucun rendez-vous aujourd&apos;hui</p>
            <p className="text-sm text-muted-foreground mt-1">
              Les rendez-vous planifiés apparaîtront ici
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {appointments.map((appointment) => {
            const statusStyle = STATUS_STYLES[appointment.status] || STATUS_STYLES.pending;
            const isActionable = appointment.status !== 'completed' && appointment.status !== 'cancelled';

            return (
              <Card key={appointment.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    {/* Time and Status */}
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2 min-w-[80px]">
                        <Clock className="h-4 w-4 text-muted-foreground" />
                        <span className="font-mono font-semibold">
                          {appointment.appointmentTime.slice(0, 5)}
                        </span>
                      </div>
                      <Badge className={`${statusStyle.bg} ${statusStyle.text}`}>
                        {statusStyle.label}
                      </Badge>
                    </div>

                    {/* Citizen Info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{appointment.citizenName}</span>
                      </div>
                      <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                        {appointment.citizenPhone && (
                          <span className="flex items-center gap-1">
                            <Phone className="h-3 w-3" />
                            {appointment.citizenPhone}
                          </span>
                        )}
                        {appointment.citizenEmail && (
                          <span className="flex items-center gap-1">
                            <Mail className="h-3 w-3" />
                            {appointment.citizenEmail}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <FileText className="h-3 w-3" />
                          {appointment.reference}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleView(appointment)}
                      >
                        <Eye className="h-4 w-4 mr-1" />
                        Voir
                      </Button>
                      {isActionable && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-green-600 border-green-200 hover:bg-green-50"
                            onClick={() => handleComplete(appointment.id)}
                            disabled={completeMutation.isPending}
                          >
                            <CheckCircle2 className="h-4 w-4 mr-1" />
                            Terminer
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-red-600 border-red-200 hover:bg-red-50"
                            onClick={() => handleCancelClick(appointment.id)}
                            disabled={cancelMutation.isPending}
                          >
                            <CalendarX className="h-4 w-4 mr-1" />
                            Annuler
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Preview Sheet */}
      <AppointmentPreviewSheet
        appointment={selectedAppointment}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        entityCode={entityCode}
        onRescheduleSuccess={() => refetch()}
      />

      {/* Cancel Confirmation Dialog */}
      <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Annuler le rendez-vous?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action annulera le rendez-vous. Le citoyen sera notifié de
              l&apos;annulation.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Non, garder</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Oui, annuler
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default TodayTab;
