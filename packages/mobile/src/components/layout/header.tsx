/**
 * Custom header with back navigation and optional right action
 *
 * Uses react-native-paper Appbar for Material Design 3 styling and
 * expo-router for back navigation.
 */

import { Appbar } from 'react-native-paper';
import { router } from 'expo-router';

import { useAppTheme } from '@core/theme';

interface HeaderProps {
  /** Screen title. */
  title: string;
  /** Show the back arrow. Defaults to false. */
  showBack?: boolean;
  /** Custom back handler. Falls back to expo-router `router.back()`. */
  onBack?: () => void;
  /** Optional node rendered on the right side of the header (e.g. icon button). */
  rightAction?: React.ReactNode;
}

export function Header({ title, showBack = false, onBack, rightAction }: HeaderProps) {
  const { colors } = useAppTheme();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      router.back();
    }
  };

  return (
    <Appbar.Header
      style={{ backgroundColor: colors.surface }}
      statusBarHeight={0}
    >
      {showBack && <Appbar.BackAction onPress={handleBack} color={colors.onSurface} />}
      <Appbar.Content title={title} titleStyle={{ color: colors.onSurface }} />
      {rightAction}
    </Appbar.Header>
  );
}
