import { setRequestLocale } from 'next-intl/server';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { NetworkStatus } from '@/modules/inspections/components/NetworkStatus';

export default async function DashboardRouteLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <DashboardLayout>
      <NetworkStatus />
      {children}
    </DashboardLayout>
  );
}
