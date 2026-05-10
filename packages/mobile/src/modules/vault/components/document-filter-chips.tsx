/**
 * Vault filter chips — tab-aware.
 *
 *  - On the **uploads** tab the chips filter by `category`
 *    (identity / vehicle / legal / financial / ... / other) — same taxonomy
 *    as the web Personal tab. Maps to backend `?category=…`.
 *  - On the **generated** tab the chips filter by `generation_type`
 *    grouped to user-friendly buckets (Recibos / Certificados / ...).
 *    Maps to backend `?generation_type=…`.
 *
 * Visual: forces both label and outline colors so outlined chips remain
 * visible on the dark theme (Paper's default uses surface, which on dark
 * collapses to nearly the background).
 */

import React from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Chip } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';

export type VaultCategoryFilter =
  | 'all'
  | 'identity'
  | 'vehicle'
  | 'legal'
  | 'financial'
  | 'administrative'
  | 'medical'
  | 'education'
  | 'photo'
  | 'business'
  | 'employment'
  | 'other';

export type VaultGenerationFilter =
  | 'all'
  | 'receipts'
  | 'certificates'
  | 'attestations'
  | 'summaries'
  | 'confirmations';

const CATEGORY_OPTIONS: VaultCategoryFilter[] = [
  'all',
  'identity',
  'vehicle',
  'legal',
  'financial',
  'administrative',
  'medical',
  'education',
  'photo',
  'business',
  'employment',
  'other',
];

const GENERATION_OPTIONS: VaultGenerationFilter[] = [
  'all',
  'receipts',
  'certificates',
  'attestations',
  'summaries',
  'confirmations',
];

interface UploadsProps {
  tab: 'uploads';
  value: VaultCategoryFilter;
  onChange: (value: VaultCategoryFilter) => void;
}

interface GeneratedProps {
  tab: 'generated';
  value: VaultGenerationFilter;
  onChange: (value: VaultGenerationFilter) => void;
}

export type DocumentFilterChipsProps = UploadsProps | GeneratedProps;

export function DocumentFilterChips(props: DocumentFilterChipsProps) {
  const { t } = useTranslation();
  const { colors } = useAppTheme();

  const options =
    props.tab === 'uploads' ? CATEGORY_OPTIONS : GENERATION_OPTIONS;
  const i18nNs = props.tab === 'uploads' ? 'vault.categories' : 'vault.generationTypes';

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {options.map((opt) => {
        const selected = props.value === opt;
        // Note: `compact` was previously set on Paper's <Chip>, but combined
        // with `mode="outlined"` + `showSelectedCheck={false}` it raced with
        // the horizontal ScrollView's first measurement and rendered empty
        // pill shapes until the user tapped one (see debug/tesoro/m3.jpg).
        // We drop `compact` and shrink the container padding ourselves —
        // identical visual density, no first-render glitch.
        return (
          <View key={opt} style={styles.chip}>
            <Chip
              selected={selected}
              onPress={() =>
                (props.onChange as (v: typeof opt) => void)(opt)
              }
              mode={selected ? 'flat' : 'outlined'}
              showSelectedCheck={false}
              style={[
                styles.chipInner,
                selected
                  ? { backgroundColor: colors.primaryContainer }
                  : { backgroundColor: colors.surface, borderColor: colors.outline },
              ]}
              textStyle={{
                color: selected ? colors.onPrimaryContainer : colors.onSurface,
                fontWeight: selected ? '600' : '500',
                fontSize: 13,
              }}
            >
              {t(`${i18nNs}.${opt}`)}
            </Chip>
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 8,
  },
  chip: {
    marginRight: 8,
  },
  // Shrinks the standard Chip height to match the prior `compact` look
  // without using the prop that caused the empty-pill first-render bug.
  chipInner: {
    height: 32,
  },
});
