import { useState, useEffect, useCallback } from 'react';
import { StyleSheet, View, FlatList, Pressable } from 'react-native';
import { Text, Button, Divider, ActivityIndicator } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatDate } from '@core/utils/format';
import type {
  AppointmentLocationsResponse,
  AppointmentLocation,
  AvailableDaysResponse,
  AvailableDay,
  AvailableSlotsResponse,
  AvailableSlot,
  AppointmentSelectionRequest,
  WizardAppointmentData,
} from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepAppointmentProps {
  getLocations: () => Promise<AppointmentLocationsResponse>;
  getAvailableDays: (locationId: string, fromDate?: string) => Promise<AvailableDaysResponse>;
  getAvailableSlots: (locationId: string, fromDate?: string) => Promise<AvailableSlotsResponse>;
  saveAppointment: (data: AppointmentSelectionRequest) => Promise<void>;
  currentAppointment?: WizardAppointmentData;
  isSaving: boolean;
}

type SubStep = 'location' | 'day' | 'slot';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepAppointment({
  getLocations,
  getAvailableDays,
  getAvailableSlots,
  saveAppointment,
  currentAppointment,
  isSaving,
}: StepAppointmentProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  // Sub-step navigation
  const [subStep, setSubStep] = useState<SubStep>('location');

  // Data
  const [locations, setLocations] = useState<AppointmentLocation[]>([]);
  const [days, setDays] = useState<AvailableDay[]>([]);
  const [slots, setSlots] = useState<AvailableSlot[]>([]);

  // Selections
  const [selectedLocation, setSelectedLocation] = useState<AppointmentLocation | null>(null);
  const [selectedDay, setSelectedDay] = useState<AvailableDay | null>(null);

  // Loading
  const [loadingLocations, setLoadingLocations] = useState(false);
  const [loadingDays, setLoadingDays] = useState(false);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Load locations on mount ────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoadingLocations(true);
    setError(null);
    getLocations()
      .then((res) => {
        if (!cancelled) setLocations(res.locations);
      })
      .catch(() => {
        if (!cancelled) setError(t('wizard.appointment.errorLocations'));
      })
      .finally(() => {
        if (!cancelled) setLoadingLocations(false);
      });
    return () => { cancelled = true; };
  }, [getLocations, t]);

  // ── Load days when location selected ───────────────────────────────────
  const handleSelectLocation = useCallback(
    (location: AppointmentLocation) => {
      setSelectedLocation(location);
      setSelectedDay(null);
      setDays([]);
      setSlots([]);
      setSubStep('day');
      setLoadingDays(true);
      setError(null);
      getAvailableDays(location.id)
        .then((res) => setDays(res.days))
        .catch(() => setError(t('wizard.appointment.errorDays')))
        .finally(() => setLoadingDays(false));
    },
    [getAvailableDays, t],
  );

  // ── Load slots when day selected ───────────────────────────────────────
  const handleSelectDay = useCallback(
    (day: AvailableDay) => {
      if (!selectedLocation) return;
      setSelectedDay(day);
      setSlots([]);
      setSubStep('slot');
      setLoadingSlots(true);
      setError(null);
      getAvailableSlots(selectedLocation.id, day.slot_date)
        .then((res) => setSlots(res.slots))
        .catch(() => setError(t('wizard.appointment.errorSlots')))
        .finally(() => setLoadingSlots(false));
    },
    [selectedLocation, getAvailableSlots, t],
  );

  // ── Save appointment when slot selected ────────────────────────────────
  const handleSelectSlot = useCallback(
    (slot: AvailableSlot) => {
      if (!selectedLocation) return;
      saveAppointment({
        entity_location_id: selectedLocation.id,
        location_name: selectedLocation.location_name,
        city: selectedLocation.city,
        appointment_date: slot.slot_date,
        appointment_time: slot.slot_time,
      });
    },
    [selectedLocation, saveAppointment],
  );

  // ── Back navigation ────────────────────────────────────────────────────
  const handleBack = useCallback(() => {
    if (subStep === 'slot') {
      setSubStep('day');
      setSlots([]);
    } else if (subStep === 'day') {
      setSubStep('location');
      setDays([]);
      setSelectedLocation(null);
    }
  }, [subStep]);

  // ── Sub-step title ─────────────────────────────────────────────────────
  const subStepTitle = {
    location: t('wizard.appointment.selectLocation'),
    day: t('wizard.appointment.selectDay'),
    slot: t('wizard.appointment.selectSlot'),
  }[subStep];

  // ── Current appointment summary ────────────────────────────────────────
  if (currentAppointment && subStep === 'location') {
    return (
      <View style={{ padding: spacing.md }}>
        <View
          style={[
            styles.confirmationCard,
            {
              backgroundColor: colors.primaryContainer,
              borderRadius: borderRadius.sm,
              padding: spacing.md,
            },
          ]}
        >
          <View style={styles.confirmationHeader}>
            <MaterialCommunityIcons
              name="check-circle"
              size={24}
              color={colors.primary}
            />
            <Text
              variant="titleSmall"
              style={{ color: colors.onPrimaryContainer, fontWeight: '600', marginLeft: spacing.sm }}
            >
              {t('wizard.appointment.confirmed')}
            </Text>
          </View>
          <Divider style={{ marginVertical: spacing.sm }} />
          <View style={styles.detailRow}>
            <MaterialCommunityIcons name="map-marker" size={16} color={colors.onPrimaryContainer} />
            <Text variant="bodyMedium" style={{ color: colors.onPrimaryContainer, marginLeft: spacing.sm, flex: 1 }}>
              {currentAppointment.location_name} — {currentAppointment.city}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <MaterialCommunityIcons name="calendar" size={16} color={colors.onPrimaryContainer} />
            <Text variant="bodyMedium" style={{ color: colors.onPrimaryContainer, marginLeft: spacing.sm }}>
              {formatDate(currentAppointment.appointment_date, 'EEEE dd MMMM yyyy')}
            </Text>
          </View>
          <View style={styles.detailRow}>
            <MaterialCommunityIcons name="clock-outline" size={16} color={colors.onPrimaryContainer} />
            <Text variant="bodyMedium" style={{ color: colors.onPrimaryContainer, marginLeft: spacing.sm }}>
              {currentAppointment.appointment_time}
            </Text>
          </View>
        </View>
        <Button
          mode="outlined"
          onPress={() => setSubStep('location')}
          style={{ marginTop: spacing.md, borderRadius: borderRadius.sm }}
          icon="pencil"
        >
          {t('wizard.appointment.change')}
        </Button>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, paddingHorizontal: spacing.md }}>
      {/* Sub-header with back + title */}
      <View style={[styles.subHeader, { paddingVertical: spacing.sm }]}>
        {subStep !== 'location' && (
          <Pressable onPress={handleBack} hitSlop={8}>
            <MaterialCommunityIcons name="arrow-left" size={24} color={colors.onSurface} />
          </Pressable>
        )}
        <Text
          variant="titleSmall"
          style={{
            color: colors.onSurface,
            fontWeight: '600',
            marginLeft: subStep !== 'location' ? spacing.sm : 0,
            flex: 1,
          }}
        >
          {subStepTitle}
        </Text>
        {selectedLocation && subStep !== 'location' && (
          <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>
            {selectedLocation.location_name}
          </Text>
        )}
      </View>
      <Divider />

      {/* Error */}
      {error && (
        <View style={[styles.errorRow, { backgroundColor: colors.errorContainer, padding: spacing.sm, marginTop: spacing.sm, borderRadius: borderRadius.sm }]}>
          <MaterialCommunityIcons name="alert-circle" size={16} color={colors.error} />
          <Text variant="bodySmall" style={{ color: colors.error, marginLeft: spacing.sm, flex: 1 }}>
            {error}
          </Text>
        </View>
      )}

      {/* Location list */}
      {subStep === 'location' && (
        loadingLocations ? (
          <ActivityIndicator style={{ marginTop: spacing.xl }} />
        ) : (
          <FlatList
            data={locations}
            keyExtractor={(item) => item.id}
            ItemSeparatorComponent={() => <Divider />}
            contentContainerStyle={{ paddingBottom: spacing.xl }}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => handleSelectLocation(item)}
                style={({ pressed }) => [
                  styles.listItem,
                  { paddingVertical: spacing.md, opacity: pressed ? 0.7 : 1 },
                ]}
              >
                <MaterialCommunityIcons
                  name="office-building-marker"
                  size={22}
                  color={colors.primary}
                />
                <View style={{ flex: 1, marginLeft: spacing.md }}>
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '500' }}>
                    {item.location_name}
                  </Text>
                  <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant }}>
                    {item.city}
                    {item.address ? ` — ${item.address}` : ''}
                  </Text>
                </View>
                <MaterialCommunityIcons name="chevron-right" size={20} color={colors.outline} />
              </Pressable>
            )}
          />
        )
      )}

      {/* Day list */}
      {subStep === 'day' && (
        loadingDays ? (
          <ActivityIndicator style={{ marginTop: spacing.xl }} />
        ) : (
          <FlatList
            data={days}
            keyExtractor={(item) => item.slot_date}
            ItemSeparatorComponent={() => <Divider />}
            contentContainerStyle={{ paddingBottom: spacing.xl }}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => handleSelectDay(item)}
                style={({ pressed }) => [
                  styles.listItem,
                  { paddingVertical: spacing.md, opacity: pressed ? 0.7 : 1 },
                ]}
              >
                <MaterialCommunityIcons name="calendar" size={22} color={colors.primary} />
                <View style={{ flex: 1, marginLeft: spacing.md }}>
                  <Text variant="bodyMedium" style={{ color: colors.onSurface, fontWeight: '500' }}>
                    {formatDate(item.slot_date, 'EEEE dd MMMM yyyy')}
                  </Text>
                </View>
                <View style={[styles.badge, { backgroundColor: colors.primaryContainer, borderRadius: borderRadius.xl }]}>
                  <Text variant="labelSmall" style={{ color: colors.primary, fontWeight: '600' }}>
                    {item.total_slots_remaining} {item.total_slots_remaining === 1
                      ? t('wizard.appointment.slot')
                      : t('wizard.appointment.slots')}
                  </Text>
                </View>
              </Pressable>
            )}
          />
        )
      )}

      {/* Slot grid */}
      {subStep === 'slot' && (
        loadingSlots ? (
          <ActivityIndicator style={{ marginTop: spacing.xl }} />
        ) : (
          <View style={{ paddingTop: spacing.md }}>
            {selectedDay && (
              <Text
                variant="bodySmall"
                style={{ color: colors.onSurfaceVariant, marginBottom: spacing.md }}
              >
                {formatDate(selectedDay.slot_date, 'EEEE dd MMMM yyyy')}
              </Text>
            )}
            <View style={styles.slotsGrid}>
              {slots.map((slot) => (
                <Button
                  key={`${slot.slot_date}-${slot.slot_time}`}
                  mode="outlined"
                  onPress={() => handleSelectSlot(slot)}
                  loading={isSaving}
                  disabled={isSaving || slot.slots_remaining <= 0}
                  style={[
                    styles.slotButton,
                    { borderRadius: borderRadius.sm, borderColor: colors.outline },
                  ]}
                  labelStyle={{ fontSize: 14 }}
                  compact
                >
                  {slot.slot_time}
                </Button>
              ))}
            </View>
            {slots.length === 0 && !loadingSlots && (
              <Text
                variant="bodyMedium"
                style={{ color: colors.onSurfaceVariant, textAlign: 'center', marginTop: spacing.xl }}
              >
                {t('wizard.appointment.noSlots')}
              </Text>
            )}
          </View>
        )
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  subHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
  },
  confirmationCard: {},
  confirmationHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  errorRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  slotsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  slotButton: {
    minWidth: 80,
  },
});
