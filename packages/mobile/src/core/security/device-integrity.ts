/**
 * Device integrity check — defense in depth, not first-line.
 *
 * The check answers a single yes/no question to the rest of the app:
 *   "Does this look like a real, non-rooted, non-tampered consumer device?"
 *
 * It cannot be a hard gate. A motivated attacker bypasses every probe in
 * here in minutes. Its purpose is twofold:
 *   1. **Telemetry** — emit a Sentry breadcrumb so we have a signal when
 *      a session originates from an emulator or rooted device. That helps
 *      triage fraud incidents post-hoc.
 *   2. **User awareness** — show a non-blocking informational banner so an
 *      end user who unknowingly runs the app on a compromised device gets a
 *      hint that *they* should be suspicious of the data they enter.
 *
 * What this check does NOT do:
 *   - It does NOT refuse access. Refusing emulators breaks every developer
 *     and tester; refusing rooted devices over-blocks legitimate power users.
 *   - It does NOT call any backend endpoint. The signal is fire-and-forget
 *     telemetry only.
 */

import * as Device from 'expo-device';

import { addBreadcrumb, captureMessage } from '@core/observability/sentry';

export interface DeviceIntegrityReport {
  trusted: boolean;
  /** Human-readable reasons, lowercase machine-friendly tokens. */
  reasons: readonly string[];
  /** True when this is a physical device (false on emulator/simulator). */
  isPhysical: boolean;
}

/**
 * Run the basic integrity heuristics. Returns a report; never throws.
 *
 * Heuristics deliberately conservative — false positives are costly (annoying
 * banners), false negatives are acceptable (the check is defense in depth).
 */
export async function checkDeviceIntegrity(): Promise<DeviceIntegrityReport> {
  const reasons: string[] = [];

  // 1. Physical device check. Emulators / simulators report `Device.isDevice = false`.
  const isPhysical = Device.isDevice ?? true;
  if (!isPhysical) {
    reasons.push('emulator');
  }

  // 2. Brand / model fingerprints used by emulators (Genymotion, Android SDK).
  const brand = (Device.brand ?? '').toLowerCase();
  const model = (Device.modelName ?? '').toLowerCase();
  const knownEmulatorBrands = ['google', 'generic'];
  const knownEmulatorModels = ['sdk', 'android sdk', 'emulator', 'simulator'];
  if (
    isPhysical &&
    (knownEmulatorBrands.includes(brand) ||
      knownEmulatorModels.some((m) => model.includes(m)))
  ) {
    reasons.push('suspicious-fingerprint');
  }

  // 3. (Future) iOS jailbreak / Android root detection would go here. Doing
  //    this safely needs a native module — `react-native-jail-monkey` or a
  //    custom Frida-detection — which we deliberately don't pull in for V1.

  const trusted = reasons.length === 0;
  return { trusted, reasons, isPhysical };
}

/**
 * Convenience wrapper: run the check and forward the result to telemetry.
 * Call once per cold start, after auth bootstrap.
 */
export async function reportDeviceIntegrity(): Promise<DeviceIntegrityReport> {
  const report = await checkDeviceIntegrity();
  if (!report.trusted) {
    addBreadcrumb('device-integrity', 'Untrusted device session', {
      reasons: report.reasons.join(','),
    });
    captureMessage('Untrusted device session', 'warning', {
      tag: 'device-integrity',
      extra: { reasons: report.reasons.join(','), isPhysical: report.isPhysical },
    });
  }
  return report;
}
