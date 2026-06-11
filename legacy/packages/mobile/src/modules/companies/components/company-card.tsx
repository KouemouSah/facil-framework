import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { CompanyResponse } from '../types/companies.types';

interface CompanyCardProps {
  company: CompanyResponse;
  onPress: (company: CompanyResponse) => void;
}

function CompanyCardImpl({ company, onPress }: CompanyCardProps) {
  const { colors } = useAppTheme();
  const isBundle = company.regimen_fiscal === 'bundle';

  return (
    <Pressable
      onPress={() => onPress(company)}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[styles.row, { backgroundColor: colors.surface }]}
    >
      <View style={[styles.iconWrap, { backgroundColor: `${colors.primary}1A` }]}>
        <MaterialCommunityIcons name="domain" size={24} color={colors.primary} />
      </View>
      <View style={styles.body}>
        <Text
          variant="titleSmall"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: '600' }}
        >
          {company.legal_name}
        </Text>
        <Text variant="bodySmall" numberOfLines={1} style={{ color: colors.onSurfaceVariant }}>
          {company.tax_id ?? company.nif ?? '—'}
          {company.member_count ? ` · ${company.member_count} miembros` : ''}
        </Text>
      </View>
      {isBundle ? (
        <View style={[styles.badge, { backgroundColor: colors.primaryContainer }]}>
          <Text style={{ color: colors.onPrimaryContainer, fontSize: 11, fontWeight: '700' }}>
            BUNDLE
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 64,
    alignItems: 'center',
    gap: 12,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1 },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
});

/** Memoized — the companies FlatList may rerender on filter or search changes. */
export const CompanyCard = memo(CompanyCardImpl);
