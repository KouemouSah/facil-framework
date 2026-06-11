/**
 * Auth Layout
 * Used for authentication pages (login, register, forgot password)
 * Each auth page manages its own Header/Footer and layout structure
 */

import { setRequestLocale } from 'next-intl/server';

export default async function AuthLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <>{children}</>;
}
