import { StyleSheet, View } from 'react-native';
import { Text, useTheme } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface WizardStepperProps {
  totalSteps: number;
  currentStep: number; // 0-based
  stepLabels?: string[];
}

export function WizardStepper({ totalSteps, currentStep, stepLabels }: WizardStepperProps) {
  const theme = useTheme();

  return (
    <View style={styles.container}>
      {Array.from({ length: totalSteps }).map((_, i) => {
        const isCompleted = i < currentStep;
        const isCurrent = i === currentStep;
        const isLast = i === totalSteps - 1;

        return (
          <View key={i} style={styles.stepWrapper}>
            <View style={styles.stepRow}>
              {/* Circle */}
              <View
                style={[
                  styles.circle,
                  isCompleted && { backgroundColor: theme.colors.primary },
                  isCurrent && { backgroundColor: theme.colors.primary, borderWidth: 2, borderColor: theme.colors.primary },
                  !isCompleted && !isCurrent && { backgroundColor: '#E0E0E0' },
                ]}
              >
                {isCompleted ? (
                  <MaterialCommunityIcons name="check" size={12} color="#fff" />
                ) : (
                  <Text style={[styles.stepNumber, { color: isCurrent ? '#fff' : '#9E9E9E' }]}>
                    {i + 1}
                  </Text>
                )}
              </View>
              {/* Connector line */}
              {!isLast && (
                <View style={[styles.line, { backgroundColor: isCompleted ? theme.colors.primary : '#E0E0E0' }]} />
              )}
            </View>
            {/* Optional label below current step */}
            {isCurrent && stepLabels && stepLabels[i] && (
              <Text style={[styles.label, { color: theme.colors.primary }]} numberOfLines={1}>
                {stepLabels[i]}
              </Text>
            )}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 8 },
  stepWrapper: { flex: 1, alignItems: 'center' },
  stepRow: { flexDirection: 'row', alignItems: 'center', width: '100%' },
  circle: { width: 24, height: 24, borderRadius: 12, justifyContent: 'center', alignItems: 'center', zIndex: 1 },
  stepNumber: { fontSize: 11, fontWeight: '700' },
  line: { flex: 1, height: 2, marginHorizontal: -2 },
  label: { fontSize: 9, fontWeight: '600', marginTop: 2, textAlign: 'center' },
});
