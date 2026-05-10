/**
 * Chat Tab — AI Assistant (RAG + Gemini)
 *
 * Design inspired by Claude AI mobile:
 * - Clean minimal header with Facil logo avatar
 * - Full-height message list (FlatList inverted)
 * - Bot messages with logo avatar + wide bubbles
 * - User messages right-aligned, tonal color
 * - Suggestion chips after bot responses
 * - Related services tappable
 * - Typing indicator while waiting
 * - Rounded input bar at bottom
 *
 * Uses POST /chatbot/chat (public, no auth required).
 */

import { useState, useRef, useCallback } from 'react';
import {
  StyleSheet,
  View,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Image,
  Pressable,
  Share,
} from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { Text, TextInput, IconButton, Chip, ActivityIndicator, Snackbar } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import Markdown from 'react-native-markdown-display';
import { useAppTheme } from '@core/theme';
import { useChatbot, submitFeedback } from '@modules/chatbot';
import type { ChatMessage } from '@modules/chatbot';

const BOT_AVATAR = require('../../../assets/images/icon_facil.png');

// ---------------------------------------------------------------------------
// Typing indicator (3 animated dots)
// ---------------------------------------------------------------------------

function TypingIndicator({ color }: { color: string }) {
  return (
    <View style={s.typingRow}>
      <Image source={BOT_AVATAR} style={s.msgAvatar} resizeMode="contain" />
      <View style={[s.typingBubble, { backgroundColor: color }]}>
        <ActivityIndicator size={16} />
        <Text variant="bodySmall" style={{ marginLeft: 8, opacity: 0.6 }}>...</Text>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Message bubble
// ---------------------------------------------------------------------------

// Full markdown styles matching web renderMarkdown() rules
const mdStyles = (colors: any) => ({
  body: { color: colors.onSurface, fontSize: 14, lineHeight: 22 },
  heading1: { fontSize: 18, fontWeight: '800' as const, color: colors.primary, marginTop: 12, marginBottom: 4 },
  heading2: { fontSize: 16, fontWeight: '700' as const, color: colors.primary, marginTop: 10, marginBottom: 4 },
  heading3: { fontSize: 15, fontWeight: '700' as const, color: colors.primary, marginTop: 8, marginBottom: 2 },
  heading4: { fontSize: 14, fontWeight: '600' as const, color: colors.primary, marginTop: 6, marginBottom: 2 },
  strong: { fontWeight: '700' as const },
  em: { fontStyle: 'italic' as const },
  bullet_list: { marginVertical: 4 },
  ordered_list: { marginVertical: 4 },
  list_item: { marginVertical: 2 },
  paragraph: { marginVertical: 3 },
  code_inline: { backgroundColor: colors.surfaceVariant, paddingHorizontal: 4, paddingVertical: 1, borderRadius: 4, fontFamily: 'monospace', fontSize: 13 },
  code_block: { backgroundColor: '#1E1E1E', color: '#D4D4D4', padding: 12, borderRadius: 8, fontFamily: 'monospace', fontSize: 12, marginVertical: 6 },
  fence: { backgroundColor: '#1E1E1E', color: '#D4D4D4', padding: 12, borderRadius: 8, fontFamily: 'monospace', fontSize: 12, marginVertical: 6 },
  blockquote: { borderLeftWidth: 3, borderLeftColor: colors.primary, paddingLeft: 10, marginVertical: 4, opacity: 0.85 },
  table: { borderWidth: 1, borderColor: colors.outlineVariant, borderRadius: 6, marginVertical: 6 },
  thead: { backgroundColor: colors.surfaceVariant },
  th: { padding: 6, fontWeight: '600' as const, fontSize: 12 },
  td: { padding: 6, fontSize: 12, borderTopWidth: 1, borderTopColor: colors.outlineVariant },
  link: { color: colors.primary, textDecorationLine: 'underline' as const },
  hr: { backgroundColor: colors.outlineVariant, height: 1, marginVertical: 8 },
});

function MessageBubble({
  msg,
  colors,
  conversationId,
  onSuggestion,
  onServicePress,
  onCopied,
}: {
  msg: ChatMessage;
  colors: any;
  conversationId?: string;
  onSuggestion: (text: string) => void;
  onServicePress: (id: number) => void;
  onCopied: () => void;
}) {
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleCopy = async () => {
    await Clipboard.setStringAsync(msg.text);
    onCopied();
  };

  const handleFeedback = (type: 'up' | 'down') => {
    if (feedback) return; // Already rated
    setFeedback(type);
    if (conversationId) {
      submitFeedback({
        conversation_id: conversationId,
        rating: type === 'up' ? 5 : 1,
        feedback: type === 'up' ? 'helpful' : 'not_helpful',
      });
    }
  };

  const handleShare = async () => {
    await Share.share({ message: msg.text });
  };

  if (msg.isBot) {
    return (
      <View style={s.botGroup}>
        {/* Avatar + bubble */}
        <View style={s.botRow}>
          <Image source={BOT_AVATAR} style={s.msgAvatar} resizeMode="contain" />
          <View style={[s.botBubble, { backgroundColor: colors.surfaceVariant }]}>
            <Markdown style={mdStyles(colors)}>
              {msg.text}
            </Markdown>
          </View>
        </View>

        {/* Action bar: feedback + copy + share */}
        <View style={s.msgActions}>
          <Pressable onPress={() => handleFeedback('up')} style={s.msgActionBtn}>
            <IconButton
              icon={feedback === 'up' ? 'thumb-up' : 'thumb-up-outline'}
              size={16}
              iconColor={feedback === 'up' ? colors.primary : colors.outline}
            />
          </Pressable>
          <Pressable onPress={() => handleFeedback('down')} style={s.msgActionBtn}>
            <IconButton
              icon={feedback === 'down' ? 'thumb-down' : 'thumb-down-outline'}
              size={16}
              iconColor={feedback === 'down' ? colors.error : colors.outline}
            />
          </Pressable>
          <Pressable onPress={handleCopy} style={s.msgActionBtn}>
            <IconButton icon="content-copy" size={16} iconColor={colors.outline} />
          </Pressable>
          <Pressable onPress={handleShare} style={s.msgActionBtn}>
            <IconButton icon="share-variant-outline" size={16} iconColor={colors.outline} />
          </Pressable>
        </View>

        {/* Related services */}
        {msg.relatedServices && msg.relatedServices.length > 0 && (
          <View style={s.relatedRow}>
            {msg.relatedServices.slice(0, 3).map((svc, i) => (
              <Pressable
                key={`${msg.id}-svc-${i}`}
                onPress={() => onServicePress(svc.id)}
                style={[s.relatedChip, { backgroundColor: colors.secondaryContainer }]}
              >
                <Text variant="labelSmall" style={{ color: colors.onSecondaryContainer }} numberOfLines={1}>
                  {svc.name}
                </Text>
              </Pressable>
            ))}
          </View>
        )}

        {/* Suggestion chips */}
        {msg.suggestions && msg.suggestions.length > 0 && (
          <View style={s.suggestionsRow}>
            {msg.suggestions.slice(0, 4).map((sug, i) => (
              <Chip
                key={`${msg.id}-sug-${i}`}
                onPress={() => onSuggestion(sug)}
                mode="outlined"
                compact
                style={s.suggestionChip}
                textStyle={{ fontSize: 12, color: colors.primary }}
              >
                {sug}
              </Chip>
            ))}
          </View>
        )}
      </View>
    );
  }

  // User message
  return (
    <View style={s.userRow}>
      <View style={[s.userBubble, { backgroundColor: colors.primaryContainer }]}>
        <Text variant="bodyMedium" style={{ color: colors.onPrimaryContainer, lineHeight: 22 }}>
          {msg.text}
        </Text>
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function ChatScreen() {
  const { t } = useTranslation();
  const { colors } = useAppTheme();
  const router = useRouter();
  const flatListRef = useRef<FlatList>(null);

  const { messages, isLoading, error, send, clearChat } = useChatbot();
  const [inputText, setInputText] = useState('');
  const [snackbar, setSnackbar] = useState<string | null>(null);
  const [statusText, setStatusText] = useState('');

  // Progressive status like web (searching → analyzing → generating)
  const statusTimersRef = useRef<NodeJS.Timeout[]>([]);
  const prevLoadingRef = useRef(false);

  if (isLoading && !prevLoadingRef.current) {
    prevLoadingRef.current = true;
    const steps = [
      t('chat.statusSearching') || 'Searching...',
      t('chat.statusAnalyzing') || 'Analyzing...',
      t('chat.statusGenerating') || 'Generating...',
    ];
    setStatusText(steps[0]);
    statusTimersRef.current = [
      setTimeout(() => setStatusText(steps[1]), 1500),
      setTimeout(() => setStatusText(steps[2]), 4000),
    ];
  }
  if (!isLoading && prevLoadingRef.current) {
    prevLoadingRef.current = false;
    statusTimersRef.current.forEach(clearTimeout);
    statusTimersRef.current = [];
    setStatusText('');
  }

  const handleSend = useCallback(() => {
    if (!inputText.trim() || isLoading) return;
    send(inputText);
    setInputText('');
  }, [inputText, isLoading, send]);

  const handleSuggestion = useCallback(
    (text: string) => {
      if (isLoading) return;
      send(text);
    },
    [isLoading, send],
  );

  const handleServicePress = useCallback(
    (id: number) => {
      router.push(`/(tabs)/services/${id}` as any);
    },
    [router],
  );

  // Welcome suggestions (shown when no messages yet)
  const welcomeSuggestions = [
    t('chat.suggestions.services'),
    t('chat.suggestions.documents'),
    t('chat.suggestions.payment'),
    t('chat.suggestions.status'),
  ];

  const hasMessages = messages.length > 0;

  return (
    <SafeAreaView style={[s.container, { backgroundColor: '#E8F5EC' }]} edges={['top']}>
      {/* ── Header ── */}
      <View style={[s.header, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <Image source={BOT_AVATAR} style={s.headerAvatar} resizeMode="contain" />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text variant="titleMedium" style={{ fontWeight: '600', color: colors.onSurface }}>
            {t('chat.title')}
          </Text>
          <Text variant="labelSmall" style={{ color: isLoading ? colors.primary : colors.outline }}>
            {isLoading ? statusText || t('chat.typing') : 'Facil AI'}
          </Text>
        </View>
        {hasMessages && (
          <IconButton icon="delete-outline" size={20} onPress={clearChat} iconColor={colors.outline} />
        )}
      </View>

      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        {!hasMessages ? (
          /* ── Welcome state: centered content with input inline ── */
          <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: 24 }}>
            <View style={s.emptyState}>
              <Image source={BOT_AVATAR} style={s.emptyAvatar} resizeMode="contain" />
              <Text variant="titleSmall" style={{ color: colors.onSurface, fontWeight: '600', marginTop: 12 }}>
                {t('chat.title')}
              </Text>
              <Text
                variant="bodySmall"
                style={{ color: colors.onSurfaceVariant, textAlign: 'center', marginTop: 4, marginBottom: 20 }}
              >
                {t('chat.welcome')}
              </Text>

              {/* Input bar inline (centered, send button inside, auto-expand) */}
              <View style={s.inlineInputBar}>
                <TextInput
                  value={inputText}
                  onChangeText={setInputText}
                  placeholder={t('chat.placeholder')}
                  mode="outlined"
                  style={s.input}
                  outlineStyle={{ borderRadius: 12 }}
                  multiline
                  maxLength={2000}
                  onSubmitEditing={handleSend}
                  returnKeyType="send"
                  blurOnSubmit
                  right={
                    <TextInput.Icon
                      icon="arrow-up-circle"
                      onPress={handleSend}
                      disabled={!inputText.trim() || isLoading}
                      color={inputText.trim() && !isLoading ? colors.primary : colors.outlineVariant}
                      size={28}
                    />
                  }
                />
              </View>

              {/* Suggestions below input */}
              <View style={s.welcomeGrid}>
                {welcomeSuggestions.map((sug) => (
                  <Pressable
                    key={sug}
                    onPress={() => handleSuggestion(sug)}
                    style={[s.welcomeGridItem, { borderColor: colors.outlineVariant }]}
                    android_ripple={{ color: colors.primaryContainer }}
                  >
                    <Text variant="labelMedium" style={{ color: colors.primary }}>
                      {sug}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </View>
          </View>
        ) : (
          /* ── Conversation mode: messages + input at bottom ── */
          <>
            <FlatList
              ref={flatListRef}
              data={messages}
              keyExtractor={(item) => item.id}
              renderItem={({ item }) => (
                <MessageBubble
                  msg={item}
                  colors={colors}
                  onSuggestion={handleSuggestion}
                  onServicePress={handleServicePress}
                  onCopied={() => setSnackbar(t('common.copied') || 'Copied')}
                />
              )}
              contentContainerStyle={{ padding: 16, paddingBottom: 8 }}
              onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
              ListFooterComponent={isLoading ? <TypingIndicator color={colors.surfaceVariant} /> : null}
            />

            {/* Error banner */}
            {error && (
              <View style={[s.errorBanner, { backgroundColor: colors.errorContainer }]}>
                <Text variant="labelSmall" style={{ color: colors.error }}>
                  {error === 'rate_limited' ? t('chat.rateLimited') : t('chat.errorSending')}
                </Text>
              </View>
            )}

            {/* Input at bottom (send button inside) */}
            <View style={[s.inputBar, { backgroundColor: '#E8F5EC' }]}>
              <TextInput
                value={inputText}
                onChangeText={setInputText}
                placeholder={t('chat.placeholder')}
                mode="outlined"
                style={s.input}
                outlineStyle={{ borderRadius: 12 }}
                dense
                multiline
                maxLength={2000}
                onSubmitEditing={handleSend}
                returnKeyType="send"
                blurOnSubmit
                right={
                  <TextInput.Icon
                    icon="arrow-up-circle"
                    onPress={handleSend}
                    disabled={!inputText.trim() || isLoading}
                    color={inputText.trim() && !isLoading ? colors.primary : colors.outlineVariant}
                    size={28}
                  />
                }
              />
            </View>
          </>
        )}
      </KeyboardAvoidingView>

      <Snackbar visible={!!snackbar} onDismiss={() => setSnackbar(null)} duration={2000}>
        {snackbar ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  container: { flex: 1 },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  headerAvatar: { width: 36, height: 36, borderRadius: 18 },

  // Empty state
  emptyState: {
    alignItems: 'center',
    paddingBottom: 16,
  },
  emptyAvatar: { width: 56, height: 56, borderRadius: 28 },
  welcomeGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    marginTop: 16,
    gap: 8,
  },
  welcomeGridItem: {
    borderWidth: 1,
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 16,
  },

  // Messages
  botGroup: { marginBottom: 16 },
  botRow: { flexDirection: 'row', alignItems: 'flex-start' },
  msgAvatar: { width: 28, height: 28, borderRadius: 14, marginTop: 2 },
  botBubble: {
    marginLeft: 10,
    borderRadius: 16,
    borderTopLeftRadius: 4,
    padding: 14,
    maxWidth: '82%',
  },
  relatedRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginLeft: 38,
    marginTop: 6,
    gap: 6,
  },
  relatedChip: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
  },
  msgActions: {
    flexDirection: 'row',
    marginLeft: 38,
    marginTop: 2,
    marginBottom: 4,
  },
  msgActionBtn: {
    marginRight: -8,
  },
  suggestionsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginLeft: 38,
    marginTop: 8,
    gap: 6,
  },
  suggestionChip: {},
  userRow: { alignItems: 'flex-end', marginBottom: 12 },
  userBubble: {
    borderRadius: 16,
    borderTopRightRadius: 4,
    padding: 14,
    maxWidth: '82%',
  },

  // Typing
  typingRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: 10,
    borderRadius: 16,
    borderTopLeftRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },

  // Error
  errorBanner: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    alignItems: 'center',
  },

  // Input
  inlineInputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    width: '100%',
  },
  inputBar: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  input: { flex: 1, fontSize: 15, height: 56 },
});
