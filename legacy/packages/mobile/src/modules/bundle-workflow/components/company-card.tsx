import { View, StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useAppTheme } from '@core/theme';
import type { CompanySummary } from '../types';

export function CompanyCard({ company }: { company: CompanySummary }) {
  const { colors } = useAppTheme();
  return (
    <View style={[s.card, { backgroundColor: colors.surface, borderColor: colors.outlineVariant }]}>
      <MaterialCommunityIcons name="domain" size={28} color={colors.primary} />
      <View style={{ flex: 1, marginLeft: 12 }}>
        <Text variant="titleSmall" style={{ fontWeight: '600' }}>{company.legal_name}</Text>
        {company.nif && <Text variant="labelSmall" style={{ color: colors.outline }}>NIF: {company.nif}</Text>}
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 2 }}>
          {company.registration_number && (
            <Text variant="labelSmall" style={{ color: colors.onSurfaceVariant }}>{company.registration_number}</Text>
          )}
          {company.zone_code && (
            <View style={[s.badge, { backgroundColor: colors.secondaryContainer }]}>
              <Text variant="labelSmall" style={{ color: colors.onSecondaryContainer, fontWeight: '600' }}>{company.zone_code}</Text>
            </View>
          )}
          {company.is_verified && (
            <MaterialCommunityIcons name="check-decagram" size={14} color={colors.primary} />
          )}
        </View>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', padding: 14, borderRadius: 12, borderWidth: 1 },
  badge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 6 },
});
