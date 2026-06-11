import { redirect } from 'next/navigation';

/**
 * Root page - Redirects to default locale (Spanish)
 * This ensures users always land on a localized page
 */
export default function RootPage() {
  redirect('/es');
}
