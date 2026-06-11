/**
 * DocumentListItem — flat-list row for the vault list.
 * Native Android style: 64dp item, leading icon coloured by category,
 * divider between rows, ripple on press.
 */

import React, { memo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import type { UserDocumentListItem as UserDocumentListItemT } from '../types/vault.types';

interface DocumentListItemProps {
  item: UserDocumentListItemT;
  onPress: (item: UserDocumentListItemT) => void;
  onLongPress?: (item: UserDocumentListItemT) => void;
}

const MIME_ICON: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = {
  'application/pdf': 'file-pdf-box',
  'image/jpeg': 'file-image',
  'image/png': 'file-image',
  'image/webp': 'file-image',
};

const CATEGORY_COLOR: Record<string, string> = {
  identity: '#1565C0',
  vehicle: '#7B1FA2',
  residence: '#388E3C',
  commerce: '#F57C00',
  fiscal: '#5D4037',
  default: '#9E9E9E',
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86_400_000);
  if (days < 1) return 'today';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  if (days < 365) return `${Math.floor(days / 30)}mo`;
  return `${Math.floor(days / 365)}y`;
}

function expiryBadge(item: UserDocumentListItemT, errorColor: string, warningColor: string) {
  const status = item.expiry_status;
  if (status === 'expired') {
    return { color: errorColor, label: 'expired' };
  }
  if (status === 'expiring_soon') {
    const days = item.days_until_expiry ?? 0;
    return { color: warningColor, label: `${days}d` };
  }
  return null;
}

function DocumentListItemImpl({ item, onPress, onLongPress }: DocumentListItemProps) {
  const { colors } = useAppTheme();
  const iconName = MIME_ICON[item.mime_type] ?? 'file-document-outline';
  const categoryColor =
    CATEGORY_COLOR[item.category ?? 'default'] ?? CATEGORY_COLOR.default;
  const badge = expiryBadge(item, colors.error, '#F57C00');

  return (
    <Pressable
      onPress={() => onPress(item)}
      onLongPress={onLongPress ? () => onLongPress(item) : undefined}
      android_ripple={{ color: colors.surfaceVariant }}
      style={[styles.row, { backgroundColor: colors.surface }]}
    >
      <View style={[styles.iconWrap, { backgroundColor: `${categoryColor}1A` }]}>
        <MaterialCommunityIcons name={iconName} size={24} color={categoryColor} />
      </View>
      <View style={styles.body}>
        <Text
          variant="titleSmall"
          numberOfLines={1}
          style={{ color: colors.onSurface, fontWeight: '600' }}
        >
          {item.display_name || item.file_name}
        </Text>
        <Text variant="bodySmall" numberOfLines={1} style={{ color: colors.onSurfaceVariant }}>
          {item.document_type ?? '—'} · {relativeTime(item.created_at)}
        </Text>
      </View>
      {badge ? (
        <View style={[styles.badge, { backgroundColor: badge.color }]}>
          <Text style={styles.badgeText}>{badge.label}</Text>
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
  body: {
    flex: 1,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    minWidth: 36,
    alignItems: 'center',
  },
  badgeText: {
    color: 'white',
    fontSize: 11,
    fontWeight: '700',
  },
});

/** Memoized — vault list re-renders on tab switch + cache refresh. */
export const DocumentListItem = memo(DocumentListItemImpl);
