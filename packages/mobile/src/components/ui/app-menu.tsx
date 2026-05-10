/**
 * App Menu — Bottom sheet navigation accessible from any sub-page
 *
 * Shows the 5 main navigation items when the bottom tab bar is hidden
 * (stack screens like Licencias, Directorio, etc.)
 */

import React, { useState } from 'react';
import { StyleSheet, Pressable } from 'react-native';
import { Text, Portal, Modal, IconButton } from 'react-native-paper';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

const MENU_ITEMS = [
  { route: '/(tabs)', icon: 'home' as const, labelKey: 'home.title' },
  { route: '/(tabs)/services', icon: 'magnify' as const, labelKey: 'services.title' },
  { route: '/(tabs)/chat', icon: 'star-four-points' as const, labelKey: 'chat.title' },
  { route: '/(tabs)/guide', icon: 'book-open-outline' as const, labelKey: 'guide.title' },
  { route: '/licencias', icon: 'store-outline' as const, labelKey: 'licenses.title' },
  { route: '/directorio', icon: 'office-building-outline' as const, labelKey: 'directory.title' },
];

export function AppMenuButton() {
  const { colors } = useAppTheme();
  const { t } = useTranslation();
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  return (
    <>
      <IconButton
        icon="menu"
        size={22}
        onPress={() => setVisible(true)}
        iconColor={colors.onSurface}
      />
      <Portal>
        <Modal
          visible={visible}
          onDismiss={() => setVisible(false)}
          contentContainerStyle={[s.modal, { backgroundColor: colors.surface }]}
        >
          <Text variant="titleSmall" style={{ fontWeight: '600', color: colors.onSurface, marginBottom: 12 }}>
            Menu
          </Text>
          {MENU_ITEMS.map((item) => (
            <Pressable
              key={item.route}
              onPress={() => { setVisible(false); router.push(item.route as any); }}
              style={s.menuItem}
              android_ripple={{ color: colors.primaryContainer }}
            >
              <MaterialCommunityIcons name={item.icon} size={22} color={colors.primary} />
              <Text variant="bodyMedium" style={{ marginLeft: 14, color: colors.onSurface }}>
                {t(item.labelKey)}
              </Text>
            </Pressable>
          ))}
        </Modal>
      </Portal>
    </>
  );
}

const s = StyleSheet.create({
  modal: {
    margin: 16,
    padding: 20,
    borderRadius: 16,
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 8,
  },
});
