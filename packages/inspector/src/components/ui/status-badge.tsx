import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useAppTheme } from '@core/theme';

interface Props {
  status: string;
  label: string;
  size?: 'small' | 'medium';
}

export function StatusBadge({ status, label, size = 'small' }: Props) {
  const { custom } = useAppTheme();

  const STATUS_COLORS: Record<string, string> = {
    in_progress: custom.status.inProgress,
    completed: custom.status.completed,
    mise_en_demeure: custom.status.miseEnDemeure,
    seal_proposed: custom.status.sealProposed,
    seal_approved: custom.status.sealApproved,
    seal_rejected: custom.status.sealRejected,
    cancelled: custom.status.cancelled,
    conforme: custom.status.conforme,
    non_conforme: custom.status.nonConforme,
    pending: custom.status.inProgress,
  };

  const color = STATUS_COLORS[status] ?? custom.secondary.main;

  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: color, width: size === 'small' ? 8 : 10, height: size === 'small' ? 8 : 10 }]} />
      <Text variant={size === 'small' ? 'labelSmall' : 'labelMedium'} style={{ color }}>
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  dot: { borderRadius: 5 },
});
