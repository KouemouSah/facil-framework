import React from 'react';
import { StyleSheet, View } from 'react-native';
import { Button } from 'react-native-paper';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useAppTheme } from '@core/theme';
import { useAuth } from '@core/hooks/use-auth';
import type { InspectionDetail } from '@modules/inspections/types/inspection.types';

interface Props {
  inspection: InspectionDetail;
}

export function ActionButtons({ inspection }: Props) {
  const { t } = useTranslation();
  const { colors, custom } = useAppTheme();
  const { isSupervisor } = useAuth();
  const { id, status } = inspection;

  const nav = (path: string) => router.push(path as never);

  if (status === 'in_progress') {
    return (
      <View style={styles.container}>
        <Button
          mode="contained"
          icon="check-circle"
          onPress={() => nav(`/inspection/${id}/complete`)}
          style={styles.button}
        >
          {t('inspection.complete')}
        </Button>
        <View style={styles.row}>
          <Button
            mode="outlined"
            icon="cash"
            onPress={() => nav(`/inspection/${id}/payment`)}
            style={[styles.button, { flex: 1 }]}
            textColor={colors.primary}
          >
            {t('payment.collect')}
          </Button>
          <Button
            mode="outlined"
            icon="alert-octagon"
            onPress={() => nav(`/inspection/${id}/med`)}
            style={[styles.button, { flex: 1 }]}
            textColor={custom.status.miseEnDemeure}
          >
            {t('med.title')}
          </Button>
        </View>
      </View>
    );
  }

  if (status === 'completed' && inspection.result === 'non_conforme') {
    return (
      <View style={styles.container}>
        <Button
          mode="contained"
          icon="alert-octagon"
          onPress={() => nav(`/inspection/${id}/med`)}
          buttonColor={custom.status.miseEnDemeure}
          style={styles.button}
        >
          {t('med.title')}
        </Button>
      </View>
    );
  }

  if (status === 'mise_en_demeure') {
    const deadlinePassed = inspection.mise_en_demeure_deadline
      ? new Date(inspection.mise_en_demeure_deadline) < new Date()
      : false;

    return (
      <View style={styles.container}>
        {deadlinePassed && (
          <Button
            mode="contained"
            icon="lock"
            onPress={() => nav(`/inspection/${id}/seal`)}
            buttonColor={custom.status.sealProposed}
            style={styles.button}
          >
            {t('seal.title')}
          </Button>
        )}
        <Button
          mode="outlined"
          icon="cash"
          onPress={() => nav(`/inspection/${id}/payment`)}
          style={styles.button}
          textColor={colors.primary}
        >
          {t('payment.collect')}
        </Button>
      </View>
    );
  }

  if (status === 'seal_proposed' && isSupervisor) {
    return (
      <View style={styles.container}>
        <Button
          mode="contained"
          icon="check"
          onPress={() => nav(`/inspection/${id}/seal-review`)}
          style={styles.button}
        >
          {t('seal.reviewTitle')}
        </Button>
      </View>
    );
  }

  return null;
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  button: { borderRadius: 8 },
  row: { flexDirection: 'row', gap: 8 },
});
