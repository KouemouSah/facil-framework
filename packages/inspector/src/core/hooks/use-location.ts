/**
 * useLocation Hook - GPS for field inspections
 *
 * Provides high-accuracy location for legally-binding inspections.
 * Uses Highest accuracy with 15s timeout, automatic retry if >50m,
 * and fallback to last known position.
 */

import { useCallback, useRef, useState } from 'react';
import * as Location from 'expo-location';
import { LocationAccuracy } from 'expo-location';

const GPS_TIMEOUT_MS = 15_000;
const MAX_ACCEPTABLE_ACCURACY_M = 50;
const MAX_RETRIES = 3;
const RETRY_DELAY_MS = 2_000;

interface LocationData {
  latitude: number;
  longitude: number;
  accuracy: number | null;
  timestamp: number;
  /** True when the returned position is a fallback (last known or low accuracy) */
  isApproximate: boolean;
  /** Human-readable warning when accuracy is degraded */
  warning: string | null;
}

interface UseLocationResult {
  location: LocationData | null;
  isLoading: boolean;
  error: string | null;
  requestLocation: () => Promise<LocationData | null>;
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Race getCurrentPositionAsync against a timeout.
 * Returns the location result or null if the timeout fires first.
 */
async function getPositionWithTimeout(
  timeoutMs: number,
): Promise<Location.LocationObject | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeoutPromise = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), timeoutMs);
  });

  try {
    const result = await Promise.race([
      Location.getCurrentPositionAsync({
        accuracy: LocationAccuracy.Highest,
      }),
      timeoutPromise,
    ]);
    return result;
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

export function useLocation(): UseLocationResult {
  const [location, setLocation] = useState<LocationData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isRequesting = useRef(false);

  const requestLocation = useCallback(async (): Promise<LocationData | null> => {
    // Prevent concurrent requests
    if (isRequesting.current) return null;
    isRequesting.current = true;
    setIsLoading(true);
    setError(null);

    try {
      // -- Permission check --
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setError('Permiso de ubicacion denegado');
        setIsLoading(false);
        isRequesting.current = false;
        return null;
      }

      // -- Check if background permission may be needed for best foreground accuracy --
      const fgPerms = await Location.getForegroundPermissionsAsync();
      if (!fgPerms.canAskAgain && fgPerms.status !== 'granted') {
        setError('Permiso de ubicacion denegado permanentemente');
        setIsLoading(false);
        isRequesting.current = false;
        return null;
      }

      // -- Attempt high-accuracy position with retries --
      let bestResult: Location.LocationObject | null = null;
      let warning: string | null = null;

      for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
        const result = await getPositionWithTimeout(GPS_TIMEOUT_MS);

        if (result === null) {
          // Timeout - fall through to fallback
          warning = 'GPS timeout - usando ultima posicion conocida';
          break;
        }

        const acc = result.coords.accuracy ?? Infinity;

        if (acc <= MAX_ACCEPTABLE_ACCURACY_M) {
          // Good accuracy - use immediately
          bestResult = result;
          warning = null;
          break;
        }

        // Track best result so far (lowest accuracy number = most precise)
        if (
          !bestResult ||
          acc < (bestResult.coords.accuracy ?? Infinity)
        ) {
          bestResult = result;
        }

        // If we have more retries, wait before next attempt
        if (attempt < MAX_RETRIES - 1) {
          await delay(RETRY_DELAY_MS);
        } else {
          warning = `Precision GPS limitada: ${Math.round(acc)}m (maximo aceptable: ${MAX_ACCEPTABLE_ACCURACY_M}m)`;
        }
      }

      // -- Fallback to last known position if no result --
      if (!bestResult) {
        const lastKnown = await Location.getLastKnownPositionAsync({
          maxAge: 5 * 60 * 1000, // 5 minutes
          requiredAccuracy: 200, // Accept up to 200m for fallback
        });

        if (lastKnown) {
          const data: LocationData = {
            latitude: lastKnown.coords.latitude,
            longitude: lastKnown.coords.longitude,
            accuracy: lastKnown.coords.accuracy,
            timestamp: lastKnown.timestamp,
            isApproximate: true,
            warning: warning ?? 'Usando ultima posicion conocida',
          };
          setLocation(data);
          setIsLoading(false);
          isRequesting.current = false;
          return data;
        }

        // No position at all
        setError('No se pudo obtener la ubicacion GPS');
        setIsLoading(false);
        isRequesting.current = false;
        return null;
      }

      // -- Build result --
      const acc = bestResult.coords.accuracy ?? null;
      const isApproximate = acc !== null && acc > MAX_ACCEPTABLE_ACCURACY_M;

      const data: LocationData = {
        latitude: bestResult.coords.latitude,
        longitude: bestResult.coords.longitude,
        accuracy: acc,
        timestamp: bestResult.timestamp,
        isApproximate,
        warning,
      };

      setLocation(data);
      setIsLoading(false);
      isRequesting.current = false;
      return data;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Error obteniendo ubicacion';
      setError(message);
      setIsLoading(false);
      isRequesting.current = false;
      return null;
    }
  }, []);

  return { location, isLoading, error, requestLocation };
}
