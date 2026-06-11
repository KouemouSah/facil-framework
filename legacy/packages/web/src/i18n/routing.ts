import { defineRouting } from 'next-intl/routing';
import { createNavigation } from 'next-intl/navigation';

export const routing = defineRouting({
  // List of all locales that are supported
  locales: ['es', 'fr', 'en'],

  // Default locale (Spanish for Guinea Ecuatorial)
  defaultLocale: 'es',

  // Optional: Prefix the default locale
  localePrefix: 'always',
});

// Lightweight wrappers around Next.js' navigation APIs
// that will consider the routing configuration
export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
