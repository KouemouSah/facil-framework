/**
 * Haptic Feedback Utilities
 *
 * Provides tactile feedback for critical actions.
 * Silent no-op if hardware doesn't support vibration.
 */

import * as Haptics from 'expo-haptics';

/** Light tap — button press, toggle, selection */
export function hapticLight() {
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
}

/** Medium tap — confirmation, navigation */
export function hapticMedium() {
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
}

/** Heavy tap — destructive actions (seal, MED, delete) */
export function hapticHeavy() {
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy).catch(() => {});
}

/** Success — inspection completed, payment validated */
export function hapticSuccess() {
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
}

/** Warning — approaching deadline, low accuracy GPS */
export function hapticWarning() {
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
}

/** Error — validation failed, network error */
export function hapticError() {
  Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
}
