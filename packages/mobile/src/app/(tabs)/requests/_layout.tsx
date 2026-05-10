/**
 * Requests Stack Layout
 *
 * Nested stack navigator inside the requests tab.
 * Allows navigation from list → detail within the same tab.
 */

import { Stack } from 'expo-router';

export default function RequestsLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
