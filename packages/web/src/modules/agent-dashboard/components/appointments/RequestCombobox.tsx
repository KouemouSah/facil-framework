/**
 * RequestCombobox Component
 * Searchable dropdown for selecting assigned service requests
 *
 * @module agent-dashboard/components/appointments
 * @date 2026-01-30
 */

'use client';

import React, { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Check, ChevronsUpDown, Calendar, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Badge } from '@/components/ui/badge';
import { useMyAssignedRequests, AssignedRequestForAppointment } from '../../hooks/useAppointments';
import type { EntityCode } from '../../types';

// =============================================================================
// PROPS
// =============================================================================

interface RequestComboboxProps {
  entityCode: EntityCode;
  selectedRequest: AssignedRequestForAppointment | null;
  onSelect: (request: AssignedRequestForAppointment | null) => void;
  disabled?: boolean;
  includeWithAppointment?: boolean;
}

// =============================================================================
// COMPONENT
// =============================================================================

export function RequestCombobox({
  entityCode,
  selectedRequest,
  onSelect,
  disabled = false,
  includeWithAppointment = true,
}: RequestComboboxProps) {
  const t = useTranslations('agent.pages.appointments.scheduleTab');
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useMyAssignedRequests(entityCode, {
    includeWithAppointment,
    enabled: open, // Only fetch when dropdown is open
  });

  const requests = data?.requests || [];

  const handleSelect = (request: AssignedRequestForAppointment) => {
    onSelect(request);
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          {selectedRequest ? (
            <div className="flex items-center gap-2 truncate">
              <span className="font-mono text-sm">{selectedRequest.reference}</span>
              <span className="text-muted-foreground truncate">
                - {selectedRequest.citizenName}
              </span>
              {selectedRequest.existingAppointment && (
                <Badge variant="secondary" className="ml-1 shrink-0">
                  <Calendar className="h-3 w-3 mr-1" />
                  {selectedRequest.existingAppointment.date}
                </Badge>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground">{t('selectRequest')}</span>
          )}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[400px] p-0" align="start">
        <Command>
          <CommandInput placeholder={`${t('requestNumber')}...`} />
          <CommandList>
            {isLoading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
            ) : requests.length === 0 ? (
              <CommandEmpty>
                {t('noRequestsFound') || 'No hay solicitudes asignadas'}
              </CommandEmpty>
            ) : (
              <CommandGroup>
                {requests.map((request) => (
                  <CommandItem
                    key={request.id}
                    value={`${request.reference} ${request.citizenName}`}
                    onSelect={() => handleSelect(request)}
                    className="flex flex-col items-start py-3"
                  >
                    <div className="flex items-center w-full">
                      <Check
                        className={cn(
                          'mr-2 h-4 w-4 shrink-0',
                          selectedRequest?.id === request.id
                            ? 'opacity-100'
                            : 'opacity-0'
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-medium">
                            {request.reference}
                          </span>
                          {request.existingAppointment && (
                            <Badge
                              variant="outline"
                              className="text-xs bg-orange-50 text-orange-700 border-orange-200"
                            >
                              <Calendar className="h-3 w-3 mr-1" />
                              {request.existingAppointment.date} {request.existingAppointment.time}
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground truncate">
                          {request.citizenName}
                        </p>
                      </div>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export default RequestCombobox;
