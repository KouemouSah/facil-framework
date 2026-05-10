/**
 * Data Sections
 *
 * Renders an array of dynamic data sections returned by the backend.
 * Each section has a title and a list of label/value field pairs rendered
 * using react-native-paper List.Item for consistent density.
 */

import { View, StyleSheet } from 'react-native';
import { Text, Surface, List, Divider } from 'react-native-paper';

import { useAppTheme } from '@core/theme';
import type { DataSection } from '../types/requests.types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DataSectionsProps {
  sections: DataSection[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DataSections({ sections }: DataSectionsProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  if (sections.length === 0) {
    return null;
  }

  return (
    <View style={{ gap: spacing.sm }}>
      {sections.map((section, sectionIndex) => (
        <Surface
          key={`section-${sectionIndex}`}
          style={[
            styles.section,
            {
              borderRadius: borderRadius.md,
              backgroundColor: colors.surface,
            },
          ]}
          elevation={1}
        >
          {/* Section title */}
          <Text
            variant="titleSmall"
            style={[
              styles.sectionTitle,
              {
                color: colors.onSurface,
                paddingHorizontal: spacing.md,
                paddingTop: spacing.md,
                paddingBottom: spacing.xs,
              },
            ]}
          >
            {section.title}
          </Text>

          {/* Field rows */}
          {section.fields.map((field, fieldIndex) => (
            <View key={`field-${sectionIndex}-${fieldIndex}`}>
              {fieldIndex > 0 && (
                <Divider style={{ marginHorizontal: spacing.md }} />
              )}
              <List.Item
                title={field.label}
                description={field.value || '-'}
                titleStyle={[styles.fieldLabel, { color: colors.onSurfaceVariant }]}
                descriptionStyle={[styles.fieldValue, { color: colors.onSurface }]}
                style={styles.listItem}
              />
            </View>
          ))}
        </Surface>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  section: {
    overflow: 'hidden',
  },
  sectionTitle: {
    fontWeight: '600',
  },
  fieldLabel: {
    fontSize: 12,
  },
  fieldValue: {
    fontSize: 14,
    fontWeight: '500',
  },
  listItem: {
    paddingVertical: 6,
  },
});
