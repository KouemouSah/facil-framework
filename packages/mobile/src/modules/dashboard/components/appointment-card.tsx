import React from 'react';
import { StyleSheet, Pressable } from 'react-native';
import { Card, Text, useTheme } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { formatDate } from '@core/utils/format';
import type { DashboardUpcomingAppointment } from '../types/dashboard.types';

interface AppointmentCardProps {
  appointment: DashboardUpcomingAppointment;
}

export function AppointmentCard({ appointment }: AppointmentCardProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const router = useRouter();

  return (
    <Pressable onPress={() => router.push(`/(tabs)/requests/${appointment.request_id}`)}>
      <Card style={[styles.card, { backgroundColor: theme.colors.primaryContainer }]}>
        <Card.Content style={styles.content}>
          <MaterialCommunityIcons name="calendar-clock" size={32} color={theme.colors.primary} />
          <Text variant="titleSmall" style={{ color: theme.colors.onPrimaryContainer, fontWeight: '600', flex: 1 }}>
            {t('dashboard.upcomingAppointment')}
          </Text>
          <Text variant="bodyMedium" style={{ color: theme.colors.onPrimaryContainer }}>
            {formatDate(appointment.appointment_date, 'PPP')}
            {appointment.time ? ` · ${appointment.time}` : ''}
          </Text>
          {appointment.location && (
            <Text variant="bodySmall" style={{ color: theme.colors.onPrimaryContainer }}>
              {appointment.location}
            </Text>
          )}
          <Text variant="labelSmall" style={{ color: theme.colors.onPrimaryContainer }}>
            {appointment.workflow_label} — {appointment.request_reference}
          </Text>
        </Card.Content>
      </Card>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 12 },
  content: { gap: 4, padding: 16 },
});
