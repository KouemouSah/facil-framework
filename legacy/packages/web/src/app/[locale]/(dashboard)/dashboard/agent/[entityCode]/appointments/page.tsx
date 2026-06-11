/**
 * Generic Entity Appointments Page
 * Resolves entityCode from URL and renders AppointmentsPage
 *
 * @route /[locale]/dashboard/agent/[entityCode]/appointments
 * @date 2026-02-21
 */

'use client';

import { useParams } from 'next/navigation';
import { AppointmentsPage } from '@/modules/agent-dashboard/components/appointments';
import { slugToEntityCode } from '@/modules/agent-dashboard/utils';

export default function EntityAppointmentsPage() {
  const params = useParams();
  const entitySlug = (params?.entityCode as string) || '';
  const entityCode = slugToEntityCode(entitySlug);

  return <AppointmentsPage entityCode={entityCode} />;
}
