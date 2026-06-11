import type { Metadata } from 'next';

// Note: globals.css is imported in [locale]/layout.tsx to avoid duplication

/**
 * Root Layout
 * Defines the base HTML structure for all pages.
 * The actual locale-specific content and providers are in [locale]/layout.tsx
 *
 * Note: We use a default lang attribute here, but the [locale]/layout.tsx
 * will override it with the correct locale-specific html element.
 */

export const metadata: Metadata = {
  title: {
    template: '%s | Facil',
    default: 'Facil - Plataforma Digital AI de Tramites de Guinea Ecuatorial',
  },
  description: 'Plataforma Digital AI de Tramites de Guinea Ecuatorial',
  keywords: ['tramites', 'Guinea Ecuatorial', 'servicios', 'gobierno', 'digital'],
  authors: [{ name: 'Facil' }],
  creator: 'Facil',
  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL || 'https://taxasge.emacsah.com'),
  openGraph: {
    type: 'website',
    locale: 'es_GQ',
    siteName: 'Facil',
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // The [locale]/layout.tsx renders its own <html> and <body> tags
  // with the correct locale. This layout acts as a pass-through
  // but provides global metadata.
  return children;
}
