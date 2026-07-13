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

  // Deployment default theme (Phase A3): `branding.theme_mode` was a PHANTOM field
  // (editable, no consumer — there is no theme system yet). Apply it server-side as
  // the default: "dark" → `.dark` class; "light" → none; "auto" → a pre-paint inline
  // script picks from prefers-color-scheme (no FOUC; `suppressHydrationWarning`
  // covers the class the script may add). A user-facing toggle is a separate follow-up.
  const themeMode = b.theme_mode || "light";
  const htmlClass = themeMode === "dark" ? `${inter.variable} dark` : inter.variable;

  return (
    <html lang={locale} suppressHydrationWarning className={htmlClass}>
      <head>
        {vars && <style id="branding-vars">{`:root{${vars}}`}</style>}
        {themeMode === "auto" && (
          <script
            dangerouslySetInnerHTML={{
              __html: "try{if(matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.classList.add('dark')}catch(e){}",
            }}
          />
        )}
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
