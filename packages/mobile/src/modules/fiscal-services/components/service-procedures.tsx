/**
 * ServiceProcedures — Accordion list of procedures with numbered steps.
 *
 * Each procedure is a Paper List.Accordion showing the procedure name
 * and total estimated time. Expanded items show numbered steps with
 * title, description, and individual time estimates.
 */

import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Surface, Text, List, Divider } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { ProcedureDetailItem } from '../types/services.types';

interface ServiceProceduresProps {
  procedures: ProcedureDetailItem[];
}

export function ServiceProcedures({ procedures }: ServiceProceduresProps) {
  const { colors, spacing, borderRadius } = useAppTheme();
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  if (procedures.length === 0) {
    return null;
  }

  const toggleExpanded = (id: number) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <Surface
      style={[
        styles.container,
        {
          padding: spacing.md,
          borderRadius: borderRadius.md,
          backgroundColor: colors.surface,
        },
      ]}
      elevation={1}
    >
      {/* Section header */}
      <View style={[styles.header, { marginBottom: spacing.sm }]}>
        <MaterialCommunityIcons name="format-list-numbered" size={20} color={colors.primary} />
        <Text
          variant="titleSmall"
          style={[styles.headerText, { color: colors.onSurface, marginLeft: spacing.sm }]}
        >
          Procedimientos ({procedures.length})
        </Text>
      </View>

      <Divider style={{ marginBottom: spacing.xs }} />

      {procedures.map((proc) => (
        <List.Accordion
          key={proc.id}
          title={proc.name}
          titleNumberOfLines={2}
          titleStyle={[styles.accordionTitle, { color: colors.onSurface }]}
          description={`${proc.total_estimated_minutes} min estimados`}
          descriptionStyle={{ color: colors.onSurfaceVariant, fontSize: 12 }}
          expanded={expanded[proc.id] ?? false}
          onPress={() => toggleExpanded(proc.id)}
          left={(props) => (
            <List.Icon
              {...props}
              icon="clipboard-list"
              color={colors.primary}
            />
          )}
          style={{ backgroundColor: 'transparent', paddingHorizontal: 0 }}
        >
          {proc.steps
            .sort((a, b) => a.step_number - b.step_number)
            .map((step) => (
              <View
                key={step.id}
                style={[styles.stepRow, { paddingVertical: spacing.sm, paddingLeft: spacing.lg }]}
              >
                {/* Step number badge */}
                <View
                  style={[
                    styles.stepBadge,
                    {
                      backgroundColor: colors.primaryContainer,
                      borderRadius: borderRadius.full,
                      width: 28,
                      height: 28,
                      marginRight: spacing.sm,
                    },
                  ]}
                >
                  <Text
                    variant="labelSmall"
                    style={{ color: colors.onPrimaryContainer, fontWeight: '700' }}
                  >
                    {step.step_number}
                  </Text>
                </View>

                {/* Step content */}
                <View style={styles.stepContent}>
                  <Text
                    variant="bodyMedium"
                    style={{ color: colors.onSurface, fontWeight: '500' }}
                  >
                    {step.title}
                  </Text>

                  {step.description ? (
                    <Text
                      variant="bodySmall"
                      style={{ color: colors.onSurfaceVariant, marginTop: 2 }}
                    >
                      {step.description}
                    </Text>
                  ) : null}

                  {step.estimated_minutes > 0 && (
                    <View style={[styles.timeRow, { marginTop: spacing.xs }]}>
                      <MaterialCommunityIcons
                        name="clock-outline"
                        size={12}
                        color={colors.outline}
                      />
                      <Text
                        variant="labelSmall"
                        style={{ color: colors.outline, marginLeft: 4 }}
                      >
                        {step.estimated_minutes} min
                      </Text>
                    </View>
                  )}
                </View>
              </View>
            ))}
        </List.Accordion>
      ))}
    </Surface>
  );
}

const styles = StyleSheet.create({
  container: {},
  header: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerText: {
    fontWeight: '600',
  },
  accordionTitle: {
    fontWeight: '600',
    fontSize: 14,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  stepBadge: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepContent: {
    flex: 1,
  },
  timeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
});
