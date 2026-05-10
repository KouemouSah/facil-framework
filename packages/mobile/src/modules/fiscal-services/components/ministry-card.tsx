/**
 * MinistryCard — Grid card for a government ministry.
 *
 * Shows an icon (matched from ministry name), the ministry name,
 * and a service count badge if available.
 *
 * Icons are matched by keyword in name_es (e.g., "HACIENDA" → cash-register).
 */

import { StyleSheet, View } from 'react-native';
import { Card, Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { MinistryItem } from '../types/services.types';

/** Map keywords in ministry name_es to icons. */
const MINISTRY_KEYWORD_ICONS: {
  keyword: string;
  icon: React.ComponentProps<typeof MaterialCommunityIcons>['name'];
}[] = [
  { keyword: 'TRANSPORTE', icon: 'car' },
  { keyword: 'SEGURIDAD', icon: 'shield-account' },
  { keyword: 'HACIENDA', icon: 'cash-register' },
  { keyword: 'DEFENSA', icon: 'shield-outline' },
  { keyword: 'EDUCACION', icon: 'school' },
  { keyword: 'COMERCIO', icon: 'store' },
  { keyword: 'HIDROCARBUROS', icon: 'oil' },
  { keyword: 'OBRAS PUBLICAS', icon: 'office-building' },
  { keyword: 'ASUNTOS EXTERIORES', icon: 'earth' },
  { keyword: 'AVIACION', icon: 'airplane' },
  { keyword: 'INFORMACION', icon: 'newspaper' },
  { keyword: 'INTERIOR', icon: 'home-city' },
  { keyword: 'IGUALDAD', icon: 'account-group' },
  { keyword: 'TURISMO', icon: 'palm-tree' },
  { keyword: 'AGRICULTURA', icon: 'sprout' },
  { keyword: 'ELECTRICIDAD', icon: 'lightning-bolt' },
  { keyword: 'FUNCION PUBLICA', icon: 'badge-account' },
  { keyword: 'PRESIDENCIA', icon: 'bank' },
  { keyword: 'AYUNTAMIENTO', icon: 'city-variant' },
  { keyword: 'CAMARA DE COMERCIO', icon: 'domain' },
];

const DEFAULT_ICON: React.ComponentProps<typeof MaterialCommunityIcons>['name'] = 'office-building';

function getMinistryIcon(nameEs: string | undefined): React.ComponentProps<typeof MaterialCommunityIcons>['name'] {
  if (!nameEs) return DEFAULT_ICON;
  const upper = nameEs.toUpperCase();
  for (const { keyword, icon } of MINISTRY_KEYWORD_ICONS) {
    if (upper.includes(keyword)) {
      return icon;
    }
  }
  return DEFAULT_ICON;
}

interface MinistryCardProps {
  ministry: MinistryItem;
  onPress: () => void;
}

export function MinistryCard({ ministry, onPress }: MinistryCardProps) {
  const { colors, spacing, borderRadius } = useAppTheme();
  const { t } = useTranslation();

  const iconName = getMinistryIcon(ministry.name_es);

  // Truncate long ministry names for card display
  const displayName = ministry.name_es.length > 50
    ? ministry.name_es.slice(0, 47) + '...'
    : ministry.name_es;

  return (
    <Card
      style={[
        styles.card,
        { borderRadius: borderRadius.md, backgroundColor: colors.surface },
      ]}
      onPress={onPress}
      mode="elevated"
    >
      <Card.Content style={[styles.content, { padding: spacing.md }]}>
        {/* Icon circle */}
        <View
          style={[
            styles.iconCircle,
            {
              backgroundColor: ministry.color
                ? `${ministry.color}20`
                : colors.primaryContainer,
              borderRadius: borderRadius.full,
              width: 48,
              height: 48,
              marginBottom: spacing.sm,
            },
          ]}
        >
          <MaterialCommunityIcons
            name={iconName}
            size={24}
            color={ministry.color ?? colors.primary}
          />
        </View>

        {/* Ministry name */}
        <Text
          variant="labelMedium"
          style={[styles.name, { color: colors.onSurface }]}
          numberOfLines={3}
        >
          {displayName}
        </Text>

        {/* Service count */}
        {ministry.service_count != null && ministry.service_count > 0 && (
          <Text
            variant="labelSmall"
            style={{ color: colors.onSurfaceVariant, marginTop: spacing.xs }}
          >
            {ministry.service_count} {t('services.title').toLowerCase()}
          </Text>
        )}
      </Card.Content>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    minWidth: 140,
    elevation: 1,
  },
  content: {
    alignItems: 'center',
  },
  iconCircle: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  name: {
    fontWeight: '600',
    textAlign: 'center',
    lineHeight: 16,
  },
});
