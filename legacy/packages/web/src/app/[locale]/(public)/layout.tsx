/**
 * Public Layout
 * Used for all public pages (homepage, services, ministries, etc.)
 * Includes Header, Footer, and FloatingChatbot
 */

import { setRequestLocale } from 'next-intl/server';
import Header from '@/components/layout/Header';
import Footer from '@/components/layout/Footer';
import FloatingChatbot from '@/components/shared/FloatingChatbot';

export default async function PublicLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="flex min-h-screen flex-col print:min-h-0 print:block">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2 focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2 focus:rounded-md focus:text-sm print:hidden"
      >
        Skip to content
      </a>
      <div className="print:hidden"><Header /></div>
      <main id="main-content" className="flex-1 print:flex-none">{children}</main>
      <div className="print:hidden"><Footer /></div>
      <div className="print:hidden"><FloatingChatbot /></div>
    </div>
  );
}
