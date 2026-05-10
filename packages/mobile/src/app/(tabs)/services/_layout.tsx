/**
 * Services Stack Layout
 *
 * Nested stack inside the Services tab.
 * - index.tsx = services catalog
 * - [id].tsx = service detail (stays inside tabs → tab bar visible)
 */

import { Stack } from 'expo-router';

export default function ServicesLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="[id]" />
    </Stack>
  );
}
