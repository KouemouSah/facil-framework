import { useState, useEffect, useCallback, useMemo } from 'react';
import { StyleSheet, View, SectionList, Pressable } from 'react-native';
import { Text, Divider, ActivityIndicator } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import type {
  AvailableSitesResponse,
  SiteInfo,
  SiteSelectionRequest,
  WizardSiteSelection,
} from '../types/wizard.types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface StepSiteSelectionProps {
  getAvailableSites: () => Promise<AvailableSitesResponse>;
  saveSite: (data: SiteSelectionRequest) => Promise<void>;
  currentSite?: WizardSiteSelection;
  isSaving: boolean;
}

interface SiteSection {
  title: string;
  data: SiteInfo[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepSiteSelection({
  getAvailableSites,
  saveSite,
  currentSite,
  isSaving,
}: StepSiteSelectionProps) {
  const { t } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const [sites, setSites] = useState<SiteInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Load sites on mount ────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAvailableSites()
      .then((res) => {
        if (!cancelled) setSites(res.sites);
      })
      .catch(() => {
        if (!cancelled) setError(t('wizard.site.errorLoading'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [getAvailableSites, t]);

  // ── Group by city (SectionList data) ───────────────────────────────────
  const sections = useMemo<SiteSection[]>(() => {
    const grouped: Record<string, SiteInfo[]> = {};
    for (const site of sites) {
      const city = site.city || t('wizard.site.other');
      if (!grouped[city]) grouped[city] = [];
      grouped[city].push(site);
    }
    return Object.entries(grouped)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([title, data]) => ({ title, data }));
  }, [sites, t]);

  // ── Select site ────────────────────────────────────────────────────────
  const handleSelect = useCallback(
    (site: SiteInfo) => {
      if (isSaving) return;
      saveSite({
        entity_location_id: site.id,
        location_name: site.location_name,
        city: site.city,
        entity_code: site.entity_code,
      });
    },
    [isSaving, saveSite],
  );

  const isSelected = useCallback(
    (site: SiteInfo) => currentSite?.entity_location_id === site.id,
    [currentSite],
  );

  // ── Loading state ──────────────────────────────────────────────────────
  if (loading) {
    return (
      <View style={[styles.center, { padding: spacing.xl }]}>
        <ActivityIndicator />
        <Text variant="bodySmall" style={{ color: colors.onSurfaceVariant, marginTop: spacing.sm }}>
          {t('wizard.site.loading')}
        </Text>
      </View>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────
  if (error) {
    return (
      <View style={[styles.center, { padding: spacing.xl }]}>
        <MaterialCommunityIcons name="alert-circle" size={32} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: spacing.sm, textAlign: 'center' }}>
          {error}
        </Text>
      </View>
    );
  }

  return (
    <SectionList
      sections={sections}
      keyExtractor={(item) => item.id}
      contentContainerStyle={{ paddingBottom: spacing.xl }}
      stickySectionHeadersEnabled={false}
      ItemSeparatorComponent={() => <Divider />}
      renderSectionHeader={({ section }) => (
        <View
          style={[
            styles.sectionHeader,
            {
              backgroundColor: colors.surfaceVariant,
              paddingHorizontal: spacing.md,
              paddingVertical: spacing.sm,
            },
          ]}
        >
          <MaterialCommunityIcons name="city" size={14} color={colors.onSurfaceVariant} />
          <Text
            variant="labelMedium"
            style={{ color: colors.onSurfaceVariant, fontWeight: '600', marginLeft: spacing.sm }}
          >
            {section.title}
          </Text>
        </View>
      )}
      renderItem={({ item }) => {
        const selected = isSelected(item);
        return (
          <Pressable
            onPress={() => handleSelect(item)}
            disabled={isSaving}
            style={({ pressed }) => [
              styles.listItem,
              {
                paddingVertical: spacing.md,
                paddingHorizontal: spacing.md,
                backgroundColor: selected ? colors.primaryContainer : 'transparent',
                opacity: pressed ? 0.7 : 1,
              },
            ]}
          >
            <MaterialCommunityIcons
              name={selected ? 'check-circle' : 'map-marker-outline'}
              size={22}
              color={selected ? colors.primary : colors.outline}
            />
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <Text
                variant="bodyMedium"
                style={{
                  color: selected ? colors.onPrimaryContainer : colors.onSurface,
                  fontWeight: '500',
                }}
              >
                {item.location_name}
              </Text>
              {item.location_address && (
                <Text
                  variant="bodySmall"
                  style={{
                    color: selected ? colors.onPrimaryContainer : colors.onSurfaceVariant,
                    marginTop: 2,
                  }}
                >
                  {item.location_address}
                </Text>
              )}
            </View>
            {item.is_main_office && (
              <View
                style={[
                  styles.mainBadge,
                  { backgroundColor: colors.tertiaryContainer, borderRadius: borderRadius.xl },
                ]}
              >
                <Text variant="labelSmall" style={{ color: colors.onTertiaryContainer, fontWeight: '600' }}>
                  {t('wizard.site.mainOffice')}
                </Text>
              </View>
            )}
          </Pressable>
        );
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  listItem: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  mainBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
});
