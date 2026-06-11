/**
 * AppointmentPreviewSheet Component
 * Sheet component for viewing appointment details with reschedule functionality
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-30
 */

'use client';

import React, { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Calendar,
  Clock,
  User,
  Phone,
  Mail,
  MapPin,
  FileText,
  RefreshCw,
  ExternalLink,
} from 'lucide-react';
import Link from 'next/link';
import { useLocale } from 'next-intl';
import type { TodayAppointmentDetail } from '../../hooks/useAppointments';
import { RescheduleDialog } from './RescheduleDialog';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface AppointmentPreviewSheetProps {
  appointment: TodayAppointmentDetail | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onReschedule?: () => void;
  entityCode?: EntityCode;
  /** Called when appointment is successfully rescheduled */
  onRescheduleSuccess?: () => void;
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

export function AppointmentPreviewSheet({
  appointment,
  open,
  onOpenChange,
  onReschedule,
  entityCode,
  onRescheduleSuccess,
}: AppointmentPreviewSheetProps) {
  const locale = useLocale();
  const [rescheduleDialogOpen, setRescheduleDialogOpen] = useState(false);

  if (!appointment) return null;

  const statusStyle = STATUS_STYLES[appointment.status] || STATUS_STYLES.pending;
  const canModify = appointment.status !== 'completed' && appointment.status !== 'cancelled';

  const handleRescheduleClick = () => {
    if (entityCode) {
      // Open reschedule dialog
      setRescheduleDialogOpen(true);
    } else if (onReschedule) {
      // Fallback to old behavior if entityCode not provided
      onReschedule();
    }
  };

  const handleRescheduleSuccess = () => {
    setRescheduleDialogOpen(false);
    onRescheduleSuccess?.();
    // Close the preview sheet after successful reschedule
    onOpenChange(false);
  };

  // Format the time for display
  const formatTime = (timeStr: string) => {
    return timeStr.slice(0, 5); // HH:MM
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            Détails du Rendez-vous
            <Badge className={`${statusStyle.bg} ${statusStyle.text}`}>
              {statusStyle.label}
            </Badge>
          </SheetTitle>
          <SheetDescription>
            Référence: {appointment.reference}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Date & Time */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Date et Heure
            </h4>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-primary" />
                <span className="font-medium">Aujourd&apos;hui</span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-primary" />
                <span className="font-mono text-lg font-semibold">
                  {formatTime(appointment.appointmentTime)}
                </span>
              </div>
            </div>
          </div>

          <Separator />

          {/* Citizen Info */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Citoyen
            </h4>
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <User className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{appointment.citizenName}</span>
              </div>
              {appointment.citizenPhone && (
                <div className="flex items-center gap-3">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <a
                    href={`tel:${appointment.citizenPhone}`}
                    className="text-primary hover:underline"
                  >
                    {appointment.citizenPhone}
                  </a>
                </div>
              )}
              {appointment.citizenEmail && (
                <div className="flex items-center gap-3">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <a
                    href={`mailto:${appointment.citizenEmail}`}
                    className="text-primary hover:underline text-sm"
                  >
                    {appointment.citizenEmail}
                  </a>
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Location */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Localisation
            </h4>
            <div className="flex items-center gap-3">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              <span>{appointment.locationName}</span>
            </div>
          </div>

          <Separator />

          {/* Service Request */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
              Demande
            </h4>
            <div className="flex items-start gap-3">
              <FileText className="h-4 w-4 text-muted-foreground mt-0.5" />
              <div>
                <p className="font-medium">{appointment.reference}</p>
                <p className="text-sm text-muted-foreground">
                  {appointment.workflowCode.replace(/_/g, ' ')}
                </p>
              </div>
            </div>
          </div>

          {/* Notes */}
          {appointment.notes && (
            <>
              <Separator />
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                  Notes
                </h4>
                <p className="text-sm bg-muted p-3 rounded-lg">
                  {appointment.notes}
                </p>
              </div>
            </>
          )}

          <Separator />

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <Link
              href={`/${locale}/dashboard/agent/requests/${appointment.requestId}`}
            >
              <Button variant="outline" className="w-full">
                <ExternalLink className="h-4 w-4 mr-2" />
                Voir la demande complète
              </Button>
            </Link>

            {canModify && (onReschedule || entityCode) && (
              <Button
                variant="secondary"
                className="w-full"
                onClick={handleRescheduleClick}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reprogrammer
              </Button>
            )}
          </div>
        </div>
      </SheetContent>

      {/* Reschedule Dialog */}
      {entityCode && (
        <RescheduleDialog
          open={rescheduleDialogOpen}
          onOpenChange={setRescheduleDialogOpen}
          reservationId={appointment.id}
          currentDate={new Date().toISOString().split('T')[0]}
          currentTime={appointment.appointmentTime}
          reference={appointment.reference}
          entityCode={entityCode}
          locationId={appointment.locationId}
          onSuccess={handleRescheduleSuccess}
        />
      )}
    </Sheet>
  );
}

export default AppointmentPreviewSheet;
