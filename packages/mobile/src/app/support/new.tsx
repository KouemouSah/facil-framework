/**
 * New Support Ticket Screen — connected to `POST /support/tickets` (P6.3).
 *
 * Form fields validated against backend Pydantic constraints:
 * - subject: 5-255 characters (SupportTicketCreate.subject)
 * - description: ≥10 characters
 * - category_id: required, INTEGER (BD verified)
 * - priority: defaults to "normal" — citizens shouldn't pick `urgent` lightly,
 *   but the backend enum supports the four values.
 */

import { useMemo, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import {
  ActivityIndicator,
  Button,
  HelperText,
  IconButton,
  Menu,
  RadioButton,
  Snackbar,
  Surface,
  Text,
  TextInput,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';

import { useAppTheme } from '@core/theme';
import { AuthGuard } from '@core/auth/auth-guard';
import {
  useCreateTicket,
  useSupportCategories,
  type SupportCategory,
  type TicketPriority,
} from '@modules/support';

function pickCategoryName(category: SupportCategory, lang: string): string {
  if (lang.startsWith('fr') && category.name_fr) return category.name_fr;
  if (lang.startsWith('en') && category.name_en) return category.name_en;
  return category.name_es;
}

const PRIORITIES: TicketPriority[] = ['low', 'normal', 'high', 'urgent'];

function NewSupportTicketContent() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { colors, spacing, borderRadius } = useAppTheme();

  const categoriesQuery = useSupportCategories();
  const createTicket = useCreateTicket();

  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState<TicketPriority>('normal');
  const [snackbar, setSnackbar] = useState<string | null>(null);

  const visibleCategories = useMemo<SupportCategory[]>(
    () =>
      (categoriesQuery.data ?? [])
        .filter((c) => c.is_active && (c.target_role === 'all' || c.target_role === 'admin'))
        .sort((a, b) => a.sort_order - b.sort_order),
    [categoriesQuery.data],
  );

  const selectedCategory = useMemo(
    () => visibleCategories.find((c) => c.id === categoryId) ?? null,
    [visibleCategories, categoryId],
  );

  const subjectError = subject.length > 0 && subject.trim().length < 5;
  const descriptionError = description.length > 0 && description.trim().length < 10;
  const canSubmit =
    !!categoryId &&
    !subjectError &&
    !descriptionError &&
    subject.trim().length >= 5 &&
    description.trim().length >= 10 &&
    !createTicket.isPending;

  const handleSubmit = async () => {
    if (!canSubmit || categoryId == null) return;
    try {
      const ticket = await createTicket.mutateAsync({
        category_id: categoryId,
        subject: subject.trim(),
        description: description.trim(),
        priority,
      });
      router.replace(`/support/${ticket.id}` as never);
    } catch (e) {
      setSnackbar(
        e instanceof Error ? e.message : t('support.new.errors.submitFailed'),
      );
    }
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
          {t('support.new.title')}
        </Text>
      </View>

      <KeyboardAvoidingView
        style={styles.keyboardView}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <ScrollView
          contentContainerStyle={[styles.scrollContent, { padding: spacing.md }]}
          keyboardShouldPersistTaps="handled"
        >
          <Surface
            style={[
              styles.formCard,
              {
                padding: spacing.lg,
                borderRadius: borderRadius.lg,
                backgroundColor: colors.surface,
                gap: spacing.md,
              },
            ]}
            elevation={1}
          >
            {/* Category picker */}
            <Menu
              visible={pickerOpen}
              onDismiss={() => setPickerOpen(false)}
              anchorPosition="bottom"
              anchor={
                <Button
                  mode="outlined"
                  icon="format-list-bulleted-type"
                  onPress={() => setPickerOpen(true)}
                  contentStyle={{ justifyContent: 'flex-start' }}
                  loading={categoriesQuery.isLoading}
                  disabled={categoriesQuery.isLoading}
                >
                  {selectedCategory
                    ? pickCategoryName(selectedCategory, i18n.language)
                    : t('support.new.selectCategory')}
                </Button>
              }
            >
              {visibleCategories.length === 0 ? (
                <Menu.Item title={t('common.noResults')} disabled />
              ) : (
                visibleCategories.map((c) => (
                  <Menu.Item
                    key={c.id}
                    title={pickCategoryName(c, i18n.language)}
                    leadingIcon={c.icon ?? 'tag-outline'}
                    onPress={() => {
                      setCategoryId(c.id);
                      setPickerOpen(false);
                    }}
                  />
                ))
              )}
            </Menu>
            {!categoryId ? (
              <HelperText type="info" visible padding="none">
                {t('support.new.errors.categoryRequired')}
              </HelperText>
            ) : null}

            {/* Subject */}
            <View>
              <TextInput
                label={t('support.subject')}
                placeholder={t('support.new.subjectPlaceholder')}
                value={subject}
                onChangeText={setSubject}
                mode="outlined"
                maxLength={255}
                error={subjectError}
                returnKeyType="next"
                left={<TextInput.Icon icon="text-short" />}
              />
              <HelperText type={subjectError ? 'error' : 'info'} visible={subjectError}>
                {t('support.new.errors.subjectTooShort')}
              </HelperText>
            </View>

            {/* Description */}
            <View>
              <TextInput
                label={t('support.description')}
                placeholder={t('support.new.descriptionPlaceholder')}
                value={description}
                onChangeText={setDescription}
                mode="outlined"
                multiline
                numberOfLines={6}
                error={descriptionError}
                left={<TextInput.Icon icon="text-long" />}
                style={styles.descriptionInput}
              />
              <HelperText
                type={descriptionError ? 'error' : 'info'}
                visible={descriptionError}
              >
                {t('support.new.errors.descriptionTooShort')}
              </HelperText>
            </View>

            {/* Priority */}
            <View>
              <Text
                variant="bodyMedium"
                style={{ color: colors.outline, marginBottom: 4 }}
              >
                {t('support.priority')}
              </Text>
              <RadioButton.Group
                value={priority}
                onValueChange={(v) => setPriority(v as TicketPriority)}
              >
                {PRIORITIES.map((p) => (
                  <RadioButton.Item
                    key={p}
                    label={t(`support.priority.${p}`, { defaultValue: p })}
                    value={p}
                    position="leading"
                    style={styles.radioItem}
                  />
                ))}
              </RadioButton.Group>
            </View>

            <Button
              mode="contained"
              icon="send"
              onPress={handleSubmit}
              loading={createTicket.isPending}
              disabled={!canSubmit}
              contentStyle={{ paddingVertical: 6 }}
              style={{ borderRadius: borderRadius.sm }}
            >
              {t('support.new.submit')}
            </Button>

            {categoriesQuery.isLoading ? (
              <View style={styles.centered}>
                <ActivityIndicator color={colors.primary} />
              </View>
            ) : null}
          </Surface>
        </ScrollView>
      </KeyboardAvoidingView>

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
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingRight: 8,
  },
  keyboardView: { flex: 1 },
  scrollContent: { flexGrow: 1 },
  formCard: { width: '100%' },
  descriptionInput: { minHeight: 120 },
  radioItem: { paddingVertical: 4 },
  centered: { alignItems: 'center', paddingVertical: 4 },
});

export default function NewSupportTicketScreen() {
  return (
    <AuthGuard>
      <NewSupportTicketContent />
    </AuthGuard>
  );
}
