/**
 * ServiceDocuments — Required documents list for a fiscal service.
 *
 * Shows each required document with an icon (based on document_type),
 * name, accepted formats, and max file size.
 */

import { StyleSheet, View } from 'react-native';
import { Surface, Text, Divider } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { DocumentDetailItem } from '../types/services.types';

/** Map document_type values to MaterialCommunityIcons names. */
const DOC_TYPE_ICONS: Record<string, React.ComponentProps<typeof MaterialCommunityIcons>['name']> = {
  photo: 'file-image',
  image: 'file-image',
  scan: 'scanner',
  pdf: 'file-pdf-box',
  form: 'file-document-edit',
  certificate: 'certificate',
  id_document: 'card-account-details',
  passport: 'passport',
};

const DEFAULT_DOC_ICON: React.ComponentProps<typeof MaterialCommunityIcons>['name'] = 'file-document';

function getDocIcon(docType: string | undefined): React.ComponentProps<typeof MaterialCommunityIcons>['name'] {
  if (!docType) return DEFAULT_DOC_ICON;
  const lower = docType.toLowerCase();
  return DOC_TYPE_ICONS[lower] ?? DEFAULT_DOC_ICON;
}

interface ServiceDocumentsProps {
  documents: DocumentDetailItem[];
}

export function ServiceDocuments({ documents }: ServiceDocumentsProps) {
  const { colors, spacing, borderRadius } = useAppTheme();

  if (documents.length === 0) {
    return null;
  }

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
        <MaterialCommunityIcons name="folder-open" size={20} color={colors.primary} />
        <Text
          variant="titleSmall"
          style={[styles.headerText, { color: colors.onSurface, marginLeft: spacing.sm }]}
        >
          Documentos requeridos ({documents.length})
        </Text>
      </View>

      <Divider style={{ marginBottom: spacing.sm }} />

      {documents.map((doc, index) => (
        <View key={doc.id}>
          <View style={[styles.docRow, { paddingVertical: spacing.sm }]}>
            {/* Icon */}
            <View
              style={[
                styles.iconContainer,
                {
                  backgroundColor: colors.surfaceVariant,
                  borderRadius: borderRadius.sm,
                  width: 40,
                  height: 40,
                  marginRight: spacing.sm,
                },
              ]}
            >
              <MaterialCommunityIcons
                name={getDocIcon(doc.document_type)}
                size={20}
                color={colors.onSurfaceVariant}
              />
            </View>

            {/* Details */}
            <View style={styles.docDetails}>
              <Text
                variant="bodyMedium"
                style={{ color: colors.onSurface, fontWeight: '500' }}
                numberOfLines={2}
              >
                {doc.name}
              </Text>

              {/* Accepted formats */}
              {doc.accepted_formats && doc.accepted_formats.length > 0 && (
                <Text
                  variant="labelSmall"
                  style={{ color: colors.onSurfaceVariant, marginTop: 2 }}
                >
                  Formatos: {doc.accepted_formats.join(', ')}
                </Text>
              )}

              {/* Max size */}
              {doc.max_size_mb > 0 && (
                <Text
                  variant="labelSmall"
                  style={{ color: colors.outline, marginTop: 1 }}
                >
                  Max: {doc.max_size_mb} MB
                </Text>
              )}
            </View>
          </View>

          {index < documents.length - 1 && <Divider />}
        </View>
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
  docRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconContainer: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  docDetails: {
    flex: 1,
  },
});
