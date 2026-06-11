/**
 * Animated Section — FadeInDown on mount for dashboard sections
 * Uses react-native-reanimated for native-driven animations.
 */

import React from 'react';
import Animated, { FadeInDown, FadeIn } from 'react-native-reanimated';

interface Props {
  children: React.ReactNode;
  /** Delay in ms before animation starts (stagger sections) */
  delay?: number;
  /** Animation type */
  type?: 'fade' | 'slide';
}

export function AnimatedSection({ children, delay = 0, type = 'slide' }: Props) {
  const entering = type === 'fade'
    ? FadeIn.delay(delay).duration(300)
    : FadeInDown.delay(delay).duration(400).springify().damping(18);

  return (
    <Animated.View entering={entering}>
      {children}
    </Animated.View>
  );
}
