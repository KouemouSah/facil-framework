/**
 * useNetwork Hook
 *
 * Reactive network status hook using @react-native-community/netinfo.
 *
 * Provides real-time connectivity information for:
 * - Showing offline banners
 * - Disabling network-dependent features
 * - Queuing operations for retry when online
 * - Adjusting image quality based on connection type
 *
 * Usage:
 * ```tsx
 * const { isConnected, isInternetReachable, connectionType } = useNetwork();
 *
 * if (!isConnected) {
 *   return <OfflineBanner />;
 * }
 * ```
 */

import { useEffect, useState } from 'react';
import NetInfo, { type NetInfoState, type NetInfoStateType } from '@react-native-community/netinfo';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NetworkStatus {
  /** Whether the device has an active network connection (Wi-Fi, cellular, etc.) */
  isConnected: boolean;
  /** Whether the internet is actually reachable (not just connected to a network) */
  isInternetReachable: boolean;
  /** The type of network connection (wifi, cellular, ethernet, etc.) */
  connectionType: NetInfoStateType | null;
  /** Additional details about the connection (e.g., cellular generation) */
  details: NetInfoState['details'];
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Subscribe to real-time network status changes.
 *
 * The hook registers a NetInfo listener on mount and cleans up on unmount.
 * The initial state is fetched synchronously from NetInfo's cache when available.
 *
 * @returns Current network status
 */
export function useNetwork(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isConnected: true, // Optimistic default - assume connected until proven otherwise
    isInternetReachable: true,
    connectionType: null,
    details: null,
  });

  useEffect(() => {
    // Subscribe to network state changes
    const unsubscribe = NetInfo.addEventListener((state: NetInfoState) => {
      setStatus({
        isConnected: state.isConnected ?? false,
        isInternetReachable: state.isInternetReachable ?? false,
        connectionType: state.type,
        details: state.details,
      });
    });

    // Fetch initial state (in case the listener hasn't fired yet)
    NetInfo.fetch().then((state: NetInfoState) => {
      setStatus({
        isConnected: state.isConnected ?? false,
        isInternetReachable: state.isInternetReachable ?? false,
        connectionType: state.type,
        details: state.details,
      });
    }).catch(() => {
      // Keep optimistic defaults on fetch failure
    });

    return () => {
      unsubscribe();
    };
  }, []);

  return status;
}
