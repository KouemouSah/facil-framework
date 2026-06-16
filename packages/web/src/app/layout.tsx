import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { Providers } from "./providers";
import "./globals.css";

// Self-hosted, subset font (no layout shift, no external request) — Core Web Vitals.
const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Facil", template: "%s · Facil" },
  description: "Digital services platform",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    <html lang={locale} suppressHydrationWarning className={inter.variable}>
      <body className="font-sans">
        <NextIntlClientProvider messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
