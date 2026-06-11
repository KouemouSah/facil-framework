/**
 * Support Ticket Detail — connected to support API (P6.3).
 *
 * Reads:
 *   - GET /support/tickets/{id}             → ticket header
 *   - GET /support/tickets/{id}/messages    → thread (citizens never see is_internal)
 * Writes:
 *   - POST /support/tickets/{id}/messages   → reply (always is_internal=false)
 *   - POST /support/tickets/{id}/close      → "mark as resolved"
 */

import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import {
  ActivityIndicator,
  Button,
  IconButton,
  Snackbar,
  Surface,
  Text,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import { useAuth } from '@core/hooks/use-auth';
import { formatDate } from '@core/utils/format';
import {
  MessageBubble,
  TicketPriorityBadge,
  TicketStatusBadge,
  useCloseTicket,
  usePostTicketMessage,
  useTicket,
  useTicketMessages,
} from '@modules/support';

const TICKET_ID_RE = /^[0-9]{1,18}$/;

function SupportTicketDetailContent() {
  const params = useLocalSearchParams<{ id: string }>();
  const idRaw = params.id ?? '';
  const ticketId = TICKET_ID_RE.test(idRaw) ? Number(idRaw) : null;

  const router = useRouter();
  const { t } = useTranslation();
  const { user } = useAuth();
  const { colors, spacing, borderRadius } = useAppTheme();
  // Bottom safe-area inset — reply bar and closed bar must sit above the
  // Android gesture nav bar (see debug/tesoro/m11.jpg).
  const insets = useSafeAreaInsets();
  const scrollRef = useRef<ScrollView>(null);

  const ticketQuery = useTicket(ticketId);
  const messagesQuery = useTicketMessages(ticketId);
  const postMessage = usePostTicketMessage(ticketId ?? 0);
  const closeTicket = useCloseTicket();

  const [draft, setDraft] = useState('');
  const [snackbar, setSnackbar] = useState<string | null>(null);

  // Auto-scroll to bottom whenever the message list grows.
  useEffect(() => {
    if (!messagesQuery.data) return;
    const id = setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    return () => clearTimeout(id);
  }, [messagesQuery.data]);

  if (ticketId == null) {
    return (
      <SafeAreaView
        style={[styles.container, styles.centered, { backgroundColor: colors.background }]}
        edges={['top']}
      >
        <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
        <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12 }}>
          {t('support.detail.errorLoading')}
        </Text>
        <Button mode="outlined" style={{ marginTop: 16 }} onPress={() => router.back()}>
          {t('common.back')}
        </Button>
      </SafeAreaView>
    );
  }

  const ticket = ticketQuery.data;
  const messages = messagesQuery.data ?? [];

  const isClosed = ticket?.status === 'closed' || ticket?.status === 'resolved';
  const canSend = !isClosed && draft.trim().length > 0 && !postMessage.isPending;

  const handleSend = async () => {
    if (!canSend) return;
    try {
      await postMessage.mutateAsync({ content: draft.trim() });
      setDraft('');
    } catch (e) {
      setSnackbar(e instanceof Error ? e.message : t('errors.serverError'));
    }
  };

  const handleClose = () => {
    Alert.alert(
      t('support.detail.closeConfirm'),
      t('support.detail.closeConfirmBody'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('common.confirm'),
          style: 'destructive',
          onPress: async () => {
            try {
              await closeTicket.mutateAsync(ticketId);
            } catch (e) {
              setSnackbar(e instanceof Error ? e.message : t('errors.serverError'));
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView
      style={[styles.container, { backgroundColor: colors.background }]}
      edges={['top']}
    >
      <View
        style={[
          styles.topBar,
          { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant },
        ]}
      >
        <IconButton icon="arrow-left" size={22} onPress={() => router.back()} />
        <Text
          variant="titleMedium"
          style={{ color: colors.onSurface, fontWeight: '600', flex: 1 }}
          numberOfLines={1}
        >
          {ticket?.ticket_number ?? t('support.detail.title')}
        </Text>
      </View>

      {ticketQuery.isLoading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary} />
        </View>
      ) : ticketQuery.error || !ticket ? (
        <View style={styles.centered}>
          <MaterialCommunityIcons name="alert-circle-outline" size={48} color={colors.error} />
          <Text variant="bodyMedium" style={{ color: colors.error, marginTop: 12 }}>
            {t('support.detail.errorLoading')}
          </Text>
          <Button mode="contained" style={{ marginTop: 16 }} onPress={() => ticketQuery.refetch()}>
            {t('common.retry')}
          </Button>
        </View>
      ) : (
        <KeyboardAvoidingView
          style={styles.flex1}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 0}
        >
          <Surface
            style={[
              styles.headerCard,
              {
                marginHorizontal: spacing.md,
                marginTop: spacing.sm,
                padding: spacing.md,
                borderRadius: borderRadius.md,
                backgroundColor: colors.surface,
                gap: 6,
              },
            ]}
            elevation={0}
          >
            <Text variant="titleSmall" style={{ color: colors.onSurface }}>
              {ticket.subject}
            </Text>
            <View style={styles.badgesRow}>
              <TicketStatusBadge status={ticket.status} compact />
              <TicketPriorityBadge priority={ticket.priority} compact />
            </View>
            <Text variant="bodySmall" style={{ color: colors.outline }}>
              {ticket.category_name ?? '—'} · {formatDate(ticket.created_at)}
            </Text>
          </Surface>

          <ScrollView
            ref={scrollRef}
            style={styles.flex1}
            contentContainerStyle={[styles.thread, { paddingVertical: spacing.sm }]}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
            showsHorizontalScrollIndicator={false}
          >
            <Text
              variant="bodyMedium"
              style={[styles.description, { color: colors.onSurfaceVariant, paddingHorizontal: spacing.md }]}
            >
              {ticket.description}
            </Text>

            {messagesQuery.isLoading ? (
              <View style={styles.centered}>
                <ActivityIndicator color={colors.primary} />
              </View>
            ) : messagesQuery.error ? (
              <Text style={{ color: colors.error, textAlign: 'center', marginTop: 16 }}>
                {t('support.detail.errorLoadingMessages')}
              </Text>
            ) : (
              messages.map((m) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  isMine={user?.id ? String(m.sender_id) === String(user.id) : false}
                />
              ))
            )}
          </ScrollView>

          {/* Reply / close zone */}
          {isClosed ? (
            <View
              style={[
                styles.closedBar,
                {
                  borderTopColor: colors.outlineVariant,
                  backgroundColor: colors.surfaceVariant,
                  paddingBottom: 12 + insets.bottom,
                },
              ]}
            >
              <MaterialCommunityIcons name="lock-outline" size={18} color={colors.outline} />
              <Text style={{ color: colors.outline, marginLeft: 8 }}>
                {t('support.detail.closed')}
              </Text>
            </View>
          ) : (
            <View
              style={[
                styles.replyBar,
                {
                  borderTopColor: colors.outlineVariant,
                  backgroundColor: colors.surface,
                  padding: spacing.sm,
                  paddingBottom: spacing.sm + insets.bottom,
                },
              ]}
            >
              <TextInput
                value={draft}
                onChangeText={setDraft}
                placeholder={t('support.detail.replyPlaceholder')}
                mode="outlined"
                multiline
                // Bounded height — without this an unbounded `multiline`
                // input grows past the screen and pushes the send-button
                // column off-screen on Android (root cause of the m10
                // overflow). Internal scroll kicks in past 120dp.
                style={{ flex: 1, maxHeight: 120 }}
                returnKeyType="send"
                onSubmitEditing={handleSend}
                blurOnSubmit={false}
              />
              <View style={{ gap: 6, marginLeft: 8 }}>
                <IconButton
                  mode="contained"
                  icon="send"
                  size={22}
                  iconColor={colors.onPrimary}
                  containerColor={colors.primary}
                  disabled={!canSend}
                  onPress={handleSend}
                />
                <IconButton
                  mode="outlined"
                  icon="check-circle-outline"
                  size={20}
                  onPress={handleClose}
                  disabled={closeTicket.isPending}
                />
              </View>
            </View>
          )}
        </KeyboardAvoidingView>
      )}

      <Snackbar
        visible={!!snackbar}
        onDismiss={() => setSnackbar(null)}
        duration={4000}
      >
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  flex1: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 16 },
  headerCard: {},
  badgesRow: { flexDirection: 'row', gap: 8, marginTop: 4 },
  thread: { paddingBottom: 16 },
  description: { marginBottom: 12 },
  replyBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    borderTopWidth: 1,
    width: '100%',
  },
  closedBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderTopWidth: 1,
    paddingTop: 12,
    paddingHorizontal: 12,
    // paddingBottom computed at render with insets.bottom — see B3 fix.
  },
});

export default function SupportTicketDetailScreen() {
  return (
    <AuthGuard>
      <SupportTicketDetailContent />
    </AuthGuard>
  );
}
