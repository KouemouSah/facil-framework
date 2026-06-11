/**
 * Payments Stack Layout
 *
 * Nested stack navigator inside the (hidden) payments tab.
 * Allows list → detail navigation. The route is hidden from the tabbar
 * (see `(tabs)/_layout.tsx`) and reached via the profile screen, the
 * request detail screen, or the wizard payment-result success CTA.
 */

import { Stack } from 'expo-router';

export default function PaymentsLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
