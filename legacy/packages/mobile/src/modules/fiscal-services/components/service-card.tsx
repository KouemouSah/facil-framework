/**
 * ServiceCard — Compact card for a fiscal service item.
 *
 * Used in the popular services horizontal list and search results.
 * Shows name, ministry badge, and price (or "Gratuito" if free).
 */

import { StyleSheet, View } from 'react-native';
import { Card, Text, Chip } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatCurrency } from '@core/utils/format';

export interface ServiceCardItem {
  id: number;
  name: string;
  description?: string;
  expedition_price: number;
  renewal_price: number;
  ministry?: string;
  category?: string;
  service_type: string;
}

interface ServiceCardProps {
  service: ServiceCardItem;
  onPress: () => void;
}

export function ServiceCard({ service, onPress }: ServiceCardProps) {
  const { colors, spacing, borderRadius } = useAppTheme();
  const { t } = useTranslation();

  const isFree = service.expedition_price === 0 && service.renewal_price === 0;

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
        {/* Service name */}
        <Text
          variant="titleSmall"
          style={[styles.name, { color: colors.onSurface }]}
          numberOfLines={2}
        >
          {service.name}
        </Text>

        {/* Ministry badge */}
        {service.ministry ? (
          <Chip
            compact
            mode="flat"
            style={[
              styles.ministryChip,
              {
                backgroundColor: colors.secondaryContainer,
                marginTop: spacing.sm,
              },
            ]}
            textStyle={[styles.chipText, { color: colors.onSecondaryContainer }]}
            icon={() => (
              <MaterialCommunityIcons
                name="office-building"
                size={12}
                color={colors.onSecondaryContainer}
              />
            )}
          >
            {service.ministry}
          </Chip>
        ) : null}

        {/* Price or Gratuito */}
        <View style={[styles.priceRow, { marginTop: spacing.sm }]}>
          {isFree ? (
            <Chip
              compact
              mode="flat"
              style={[styles.freeChip, { backgroundColor: colors.primaryContainer }]}
              textStyle={{ color: colors.onPrimaryContainer, fontSize: 11 }}
            >
              {t('services.freeService')}
            </Chip>
          ) : (
            <Text
              variant="labelMedium"
              style={[styles.price, { color: colors.primary }]}
            >
              Desde {formatCurrency(service.expedition_price)}
            </Text>
          )}
        </View>
      </Card.Content>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 200,
    elevation: 1,
  },
  content: {
    gap: 2,
  },
  name: {
    fontWeight: '600',
    lineHeight: 20,
  },
  ministryChip: {
    alignSelf: 'flex-start',
    height: 24,
  },
  chipText: {
    fontSize: 10,
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  price: {
    fontWeight: '700',
  },
  freeChip: {
    alignSelf: 'flex-start',
    height: 24,
  },
});
