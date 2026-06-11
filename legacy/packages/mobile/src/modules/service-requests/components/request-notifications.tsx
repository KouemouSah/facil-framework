/**
 * Request Notifications Timeline
 *
 * Vertical timeline of citizen-visible notifications for a service request.
 * Each entry shows a dot (filled if unread), title, optional message, and
 * a relative timestamp.
 */

import { View, StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { formatRelativeTime } from '@core/utils/format';
import type { CitizenNotification } from '@modules/dashboard/types/dashboard.types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RequestNotificationsProps {
  notifications: CitizenNotification[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DOT_SIZE = 12;
const LINE_WIDTH = 2;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RequestNotifications({ notifications }: RequestNotificationsProps) {
  const { colors, spacing } = useAppTheme();
  const { t } = useTranslation();

  if (notifications.length === 0) {
    return (
      <View style={styles.empty}>
        <Text variant="bodyMedium" style={{ color: colors.outline }}>
          {t('requests.noNotifications')}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {notifications.map((notification, index) => {
        const isLast = index === notifications.length - 1;
        const isFilled = notification.is_new;

        return (
          <View key={notification.id} style={styles.row}>
            {/* Timeline column: dot + connecting line */}
            <View style={styles.timelineColumn}>
              {/* Dot */}
              <View
                style={[
                  styles.dot,
                  {
                    width: DOT_SIZE,
                    height: DOT_SIZE,
                    borderRadius: DOT_SIZE / 2,
                    backgroundColor: isFilled ? colors.primary : 'transparent',
                    borderColor: isFilled ? colors.primary : colors.outlineVariant,
                    borderWidth: isFilled ? 0 : LINE_WIDTH,
                  },
                ]}
              />

              {/* Vertical line connecting to next item */}
              {!isLast && (
                <View
                  style={[
                    styles.line,
                    {
                      backgroundColor: colors.outlineVariant,
                      width: LINE_WIDTH,
                    },
                  ]}
                />
              )}
            </View>

            {/* Content column */}
            <View
              style={[
                styles.content,
                {
                  paddingBottom: isLast ? 0 : spacing.md,
                  marginLeft: spacing.sm,
                },
              ]}
            >
              <Text
                variant="labelMedium"
                style={[
                  styles.title,
                  {
                    color: colors.onSurface,
                    fontWeight: isFilled ? '700' : '500',
                  },
                ]}
                numberOfLines={2}
              >
                {notification.title}
              </Text>

              {notification.message ? (
                <Text
                  variant="bodySmall"
                  style={{ color: colors.onSurfaceVariant, marginTop: 2 }}
                  numberOfLines={3}
                >
                  {notification.message}
                </Text>
              ) : null}

              <Text
                variant="labelSmall"
                style={{ color: colors.outline, marginTop: spacing.xs }}
              >
                {formatRelativeTime(notification.performed_at)}
              </Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {},
  empty: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  timelineColumn: {
    alignItems: 'center',
    width: DOT_SIZE,
  },
  dot: {},
  line: {
    flex: 1,
    minHeight: 20,
  },
  content: {
    flex: 1,
  },
  title: {},
});
