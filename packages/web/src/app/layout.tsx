import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { getBranding } from "@/lib/server/backend";
import { hexToHslTriplet } from "@/lib/color";
import { Toaster } from "@/components/layout/toaster";
import { Providers } from "./providers";
import "./globals.css";

// Self-hosted, subset font (no layout shift, no external request) — Core Web Vitals.
const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

// Title comes from branding (per-deployment white-label); resolved at request time.
export async function generateMetadata(): Promise<Metadata> {
  const b = await getBranding();
  const name = b.app_name || "Facil";
  return {
    title: { default: name, template: `%s · ${name}` },
    description: b.tagline || "Digital services platform",
    // Default favicon = the framework icon (P2.4); a deployment overrides via branding.
    icons: { icon: b.favicon_url || "/favicon.ico" },
  };
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  const b = await getBranding();

  // Live theme: override the stylesheet's CSS variables from branding colours.
  const primary = hexToHslTriplet(b.primary_color);
  const secondary = hexToHslTriplet(b.secondary_color);
  const vars = [
    primary && `--primary:${primary};`,
    secondary && `--secondary:${secondary};`,
  ].filter(Boolean).join("");

  return (
    <html lang={locale} suppressHydrationWarning className={inter.variable}>
      <head>
        {vars && <style id="branding-vars">{`:root{${vars}}`}</style>}
      </head>
      <body className="font-sans">
        <NextIntlClientProvider messages={messages}>
          <Providers>{children}</Providers>
          <Toaster />
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
