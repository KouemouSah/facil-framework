/**
 * Workflow Stepper
 *
 * Horizontal stepper that visualises the phases of a service request workflow.
 * Completed steps show a checkmark, the current step is filled, and future
 * steps are outlined. A connecting line joins each step.
 */

import { View, ScrollView, StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { StepperPhase } from '../types/requests.types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkflowStepperProps {
  /** Ordered list of workflow phases. */
  phases: StepperPhase[];
  /** Zero-based index of the current active phase. */
  currentIndex: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CIRCLE_SIZE = 28;
const LINE_HEIGHT = 2;

export function WorkflowStepper({ phases, currentIndex }: WorkflowStepperProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  if (phases.length === 0) {
    return null;
  }

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={[styles.container, { paddingHorizontal: spacing.sm }]}
    >
      {phases.map((phase, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;

        // Circle styles
        let circleStyle: {
          backgroundColor: string;
          borderColor: string;
          borderWidth: number;
        };
        let circleContent: React.ReactNode;

        if (isCompleted) {
          circleStyle = {
            backgroundColor: colors.primary,
            borderColor: colors.primary,
            borderWidth: 0,
          };
          circleContent = (
            <MaterialCommunityIcons name="check" size={16} color={colors.onPrimary} />
          );
        } else if (isCurrent) {
          circleStyle = {
            backgroundColor: colors.primary,
            borderColor: colors.primary,
            borderWidth: 0,
          };
          circleContent = (
            <Text style={[styles.circleNumber, { color: colors.onPrimary }]}>
              {index + 1}
            </Text>
          );
        } else {
          circleStyle = {
            backgroundColor: 'transparent',
            borderColor: colors.outlineVariant,
            borderWidth: 2,
          };
          circleContent = (
            <Text style={[styles.circleNumber, { color: colors.outline }]}>
              {index + 1}
            </Text>
          );
        }

        // Line color: completed segments are primary, the rest are muted
        const lineColor = index < currentIndex ? colors.primary : colors.outlineVariant;

        return (
          <View key={phase.id} style={styles.stepWrapper}>
            <View style={styles.stepRow}>
              {/* Connecting line before (except first step) */}
              {index > 0 && (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor: lineColor,
                      height: LINE_HEIGHT,
                    },
                  ]}
                />
              )}

              {/* Circle */}
              <View
                style={[
                  styles.circle,
                  {
                    width: CIRCLE_SIZE,
                    height: CIRCLE_SIZE,
                    borderRadius: borderRadius.full,
                    ...circleStyle,
                  },
                ]}
              >
                {circleContent}
              </View>

              {/* Connecting line after (except last step) */}
              {index < phases.length - 1 && (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor:
                        index < currentIndex ? colors.primary : colors.outlineVariant,
                      height: LINE_HEIGHT,
                    },
                  ]}
                />
              )}
            </View>

            {/* Phase title */}
            <Text
              variant="labelSmall"
              style={[
                styles.label,
                {
                  color: isCurrent || isCompleted ? colors.onSurface : colors.outline,
                  marginTop: spacing.xs,
                  fontWeight: isCurrent ? '700' : '400',
                },
              ]}
              numberOfLines={2}
            >
              {phase.title_es}
            </Text>
          </View>
        );
      })}
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 8,
  },
  stepWrapper: {
    alignItems: 'center',
    minWidth: 72,
    maxWidth: 96,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  circle: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  circleNumber: {
    fontSize: 12,
    fontWeight: '700',
  },
  line: {
    width: 24,
  },
  label: {
    textAlign: 'center',
    fontSize: 10,
  },
});
