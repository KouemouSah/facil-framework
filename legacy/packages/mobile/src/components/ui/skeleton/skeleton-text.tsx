/**
 * SkeletonText — pulsing rectangular placeholder for a single line of text.
 *
 * Uses React Native's built-in `Animated` module (1s loop, opacity 0.45 → 1)
 * so we don't pull in `react-native-reanimated` for a primitive that doesn't
 * need it. Background colour follows the theme so light + dark stay legible.
 */

import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, type DimensionValue } from 'react-native';

import { useAppTheme } from '@core/theme';

interface Props {
  /** Width — accepts a number (px) or a percentage string. */
  width?: DimensionValue;
  /** Height — pixel value (defaults to 14, matches `bodyMedium`). */
  height?: number;
  /** Border radius in px. */
  radius?: number;
  /** Bottom margin to space lines apart. */
  marginBottom?: number;
}

const PULSE_DURATION_MS = 900;

export function SkeletonText({
  width = '100%',
  height = 14,
  radius = 4,
  marginBottom = 0,
}: Props) {
  const { colors } = useAppTheme();
  const opacity = useRef(new Animated.Value(0.45)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, {
          toValue: 1,
          duration: PULSE_DURATION_MS,
          useNativeDriver: true,
        }),
        Animated.timing(opacity, {
          toValue: 0.45,
          duration: PULSE_DURATION_MS,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity]);

  return (
    <Animated.View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.bar,
        {
          width,
          height,
          borderRadius: radius,
          marginBottom,
          backgroundColor: colors.surfaceVariant,
          opacity,
        },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  bar: { overflow: 'hidden' },
});
