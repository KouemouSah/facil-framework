import { StyleSheet, View, ScrollView } from 'react-native';
import { Text, Button, Divider } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import type { InitiatePaymentResult } from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepConfirmationProps {
  result: InitiatePaymentResult;
  onViewRequest: () => void;
  onGoHome: () => void;
}

// ---------------------------------------------------------------------------
// Payment status → visual mapping
// ---------------------------------------------------------------------------

function useStatusBadge(status?: string) {
  const { colors } = useAppTheme();

  switch (status) {
    case 'completed':
      return { label: 'Completado', color: colors.primary, bg: colors.primaryContainer };
    case 'processing':
    case 'pending':
      return { label: 'Pendiente', color: colors.warning, bg: `${colors.warning}20` };
    case 'failed':
      return { label: 'Fallido', color: colors.error, bg: colors.errorContainer };
    default:
      return { label: status ?? 'Procesando', color: colors.info, bg: colors.tertiaryContainer };
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepConfirmation({
  result,
  onViewRequest,
  onGoHome,
}: StepConfirmationProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();
  const badge = useStatusBadge(result.payment_status);

  return (
    <ScrollView contentContainerStyle={[styles.container, { padding: spacing.md }]}>
      {/* Success icon */}
      <View style={[styles.iconWrapper, { marginTop: spacing.xl, marginBottom: spacing.lg }]}>
        <MaterialCommunityIcons
          name="check-circle"
          size={72}
          color={colors.primary}
        />
      </View>

      {/* Title */}
      <Text
        variant="titleLarge"
        style={{ color: colors.onSurface, fontWeight: '700', textAlign: 'center' }}
      >
        {t('wizard.confirmation.title')}
      </Text>
      <Text
        variant="bodyMedium"
        style={{ color: colors.onSurfaceVariant, textAlign: 'center', marginTop: spacing.xs }}
      >
        {result.message_es ?? t('wizard.confirmation.subtitle')}
      </Text>

      {/* Reference number */}
      {result.reference && (
        <View style={[styles.referenceCard, { backgroundColor: colors.surfaceVariant, borderRadius: borderRadius.sm, padding: spacing.md, marginTop: spacing.lg }]}>
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {t('wizard.confirmation.reference')}
          </Text>
          <Text
            variant="headlineSmall"
            style={{ color: colors.onSurface, fontWeight: '700', marginTop: spacing.xs }}
          >
            {result.reference}
          </Text>
        </View>
      )}

      {/* Payment status badge */}
      <View style={[styles.badgeRow, { marginTop: spacing.md }]}>
        <View style={[styles.statusBadge, { backgroundColor: badge.bg, borderRadius: borderRadius.xl }]}>
          <Text variant="labelMedium" style={{ color: badge.color, fontWeight: '600' }}>
            {badge.label}
          </Text>
        </View>
      </View>

      {/* Appointment details (if confirmed) */}
      {result.appointment_confirmed && (
        <>
          <Divider style={{ marginVertical: spacing.md }} />
          <Text
            variant="titleSmall"
            style={{ color: colors.onSurface, fontWeight: '600', marginBottom: spacing.sm }}
          >
            {t('wizard.confirmation.appointmentTitle')}
          </Text>
          <View style={styles.detailRow}>
            <MaterialCommunityIcons name="calendar" size={18} color={colors.primary} />
            <Text variant="bodyMedium" style={{ color: colors.onSurface, marginLeft: spacing.sm }}>
              {result.appointment_date
                ? formatDate(result.appointment_date, 'EEEE dd MMMM yyyy')
                : '—'}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <MaterialCommunityIcons name="clock-outline" size={18} color={colors.primary} />
            <Text variant="bodyMedium" style={{ color: colors.onSurface, marginLeft: spacing.sm }}>
              {result.appointment_time ?? '—'}
            </Text>
          </View>
          {result.appointment_location && (
            <View style={styles.detailRow}>
              <MaterialCommunityIcons name="map-marker" size={18} color={colors.primary} />
              <Text variant="bodyMedium" style={{ color: colors.onSurface, marginLeft: spacing.sm, flex: 1 }}>
                {result.appointment_location}
              </Text>
            </View>
          )}
        </>
      )}

      {/* Action buttons */}
      <View style={{ marginTop: spacing.xl }}>
        <Button
          mode="contained"
          onPress={onViewRequest}
          style={{ borderRadius: borderRadius.sm }}
          contentStyle={{ paddingVertical: 4 }}
          icon="file-document-outline"
        >
          {t('wizard.confirmation.viewRequest')}
        </Button>
        <Button
          mode="outlined"
          onPress={onGoHome}
          style={{ marginTop: spacing.sm, borderRadius: borderRadius.sm }}
          contentStyle={{ paddingVertical: 4 }}
          icon="home"
        >
          {t('wizard.confirmation.goHome')}
        </Button>
      </View>
    </ScrollView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
  },
  iconWrapper: {
    alignItems: 'center',
  },
  referenceCard: {
    alignItems: 'center',
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'center',
  },
  statusBadge: {
    paddingHorizontal: 14,
    paddingVertical: 4,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
  },
});
