/**
 * Dashboard Tab — Citizen Home Screen (Native Android v2)
 *
 * - App header with logo (dashboard only)
 * - Compact horizontal stats strip
 * - Inline urgent notifications (not card)
 * - Quick actions
 * - Tabs: requests / payments / notifications
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { StyleSheet, View, ScrollView, RefreshControl, Pressable, Dimensions } from 'react-native';
import { Image } from 'expo-image';
import {
  Text,
  Button,
  SegmentedButtons,
  Divider,
} from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useIsRestoring } from '@tanstack/react-query';

import { useAppTheme } from '@core/theme';
import { FullScreenSkeleton } from '@components/ui/skeleton';
import { useAuth } from '@core/hooks/use-auth';
import { setApiLocale } from '@core/api/client';
import type { SupportedLanguage } from '@core/config/types';
import { getFullName } from '@core/config/types';
import { formatCurrency } from '@core/utils/format';
import { useDashboard } from '@modules/dashboard';
import type { DashboardStats, DashboardActionRequired } from '@modules/dashboard';
import { RecentRequestsList } from '@modules/dashboard/components/recent-requests-list';
import { RecentPaymentsList } from '@modules/dashboard/components/recent-payments-list';
import { NotificationsList } from '@modules/dashboard/components/notifications-list';
import { AppointmentCard } from '@modules/dashboard/components/appointment-card';
import { QuickActions } from '@modules/dashboard/components/quick-actions';
import { NotificationBellButton } from '@modules/notifications/components/notification-bell-button';

const APP_LOGO = require('../../../assets/images/logo_hd.png');

type TabValue = 'requests' | 'payments' | 'notifications';

// ---------------------------------------------------------------------------
// Compact Stats Strip (replaces large 2x2 grid)
// ---------------------------------------------------------------------------

function CompactStats({ stats, colors, t }: {
  stats: DashboardStats;
  colors: ReturnType<typeof useAppTheme>['colors'];
  t: ReturnType<typeof useTranslation>['t'];
}) {
  const items = [
    { value: stats.active, label: t('dashboard.stats.active'), color: '#FF9800' },
    { value: stats.completed, label: t('dashboard.stats.completed'), color: colors.primary },
    { value: stats.pending_action, label: t('dashboard.stats.pendingAction'), color: '#F44336' },
    { value: formatCurrency(stats.total_paid), label: t('dashboard.stats.totalPaid'), color: colors.primary },
  ];

  return (
    <View style={styles.statsStrip}>
      {items.map((item, i) => (
        <View key={item.label} style={[styles.statItem, i < items.length - 1 && styles.statItemBorder]}>
          <Text style={[styles.statValue, { color: item.color }]}>
            {typeof item.value === 'number' ? item.value : item.value}
          </Text>
          <Text style={[styles.statLabel, { color: colors.outline }]} numberOfLines={1}>
            {item.label}
          </Text>
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Inline Urgent Notifications (replaces ActionRequiredBanner card)
// ---------------------------------------------------------------------------

function UrgentNotifications({ actions, colors, router }: {
  actions: DashboardActionRequired[];
  colors: ReturnType<typeof useAppTheme>['colors'];
  router: ReturnType<typeof useRouter>;
}) {
  if (actions.length === 0) return null;

  return (
    <View>
      {actions.map((action) => (
        <View
          key={action.request_id}
          style={[styles.urgentItem, { borderLeftColor: '#F44336' }]}
        >
          <MaterialCommunityIcons name="alert-circle" size={16} color="#F44336" />
          <Text
            variant="bodySmall"
            style={{ color: colors.onSurface, flex: 1, marginLeft: 8 }}
            numberOfLines={2}
            onPress={() => router.push(`/(tabs)/requests/${action.request_id}`)}
          >
            <Text style={{ fontWeight: '600' }}>{action.reference}</Text>
            {' — '}{action.message}
          </Text>
          <MaterialCommunityIcons
            name="chevron-right"
            size={16}
            color={colors.outline}
          />
        </View>
      ))}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Quick Action Item (native Android style)
// ---------------------------------------------------------------------------

const QUICK_ACTIONS = [
  { icon: 'file-search-outline' as const, bg: '#E8F5E9', color: '#2E7D32', labelKey: 'services', descKey: 'services_desc' },
  { icon: 'store-outline' as const, bg: '#E3F2FD', color: '#1565C0', labelKey: 'licencias', descKey: 'licencias_desc' },
  { icon: 'domain' as const, bg: '#FFF3E0', color: '#E65100', labelKey: 'empresas', descKey: 'empresas_desc' },
  { icon: 'calculator-variant-outline' as const, bg: '#F3E5F5', color: '#7B1FA2', labelKey: 'calculador', descKey: 'calculador_desc' },
] as const;

const QUICK_ACTION_ROUTES: Record<string, string> = {
  services: '/(tabs)/services',
  licencias: '/licencias',
  empresas: '/directorio',
  calculador: '/calculator',
};

// Quick action labels and descriptions are now in i18n JSON files
// under home.quickActions.{labelKey} and home.quickActions.{labelKey}Desc

// Hero slides data
interface HeroSlide {
  isLogo?: boolean;
  mainIcon?: string;
  smallIcons?: readonly string[];
  bgColor: string; bgEnd: string;
  titleKey: string; descKey: string; badge?: string;
}

const HERO_SLIDES: HeroSlide[] = [
  {
    isLogo: true,
    bgColor: '#0D6E3F', bgEnd: '#1B9E5A',
    titleKey: 'hero1', descKey: 'hero1Desc',
  },
  {
    mainIcon: 'head-lightbulb-outline',
    smallIcons: ['scale-balance', 'gavel', 'book-open-page-variant-outline'],
    bgColor: '#1565C0', bgEnd: '#42A5F5',
    titleKey: 'hero2', descKey: 'hero2Desc', badge: 'IA',
  },
  {
    mainIcon: 'account-edit-outline',
    smallIcons: ['file-sign', 'calculator-variant', 'send-check-outline'],
    bgColor: '#E65100', bgEnd: '#FF8A65',
    titleKey: 'hero3', descKey: 'hero3Desc', badge: 'PDF',
  },
];

// Hero translations are now in i18n JSON files under home.hero.{key}

const HERO_WIDTH = Dimensions.get('window').width - 32; // paddingHorizontal 16 each side

// ---------------------------------------------------------------------------
// Language selector
// ---------------------------------------------------------------------------

const LANGUAGES: { code: SupportedLanguage; label: string; flag: string }[] = [
  { code: 'es', label: 'ES', flag: '🇬🇶' },
  { code: 'fr', label: 'FR', flag: '🇫🇷' },
  { code: 'en', label: 'EN', flag: '🇬🇧' },
];

// ---------------------------------------------------------------------------
// Public Home — Redesigned Phase C
// ---------------------------------------------------------------------------

function PublicHome() {
  const { colors } = useAppTheme();
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const lang = (i18n.language || 'es') as 'es' | 'fr' | 'en';
  const [selectedLang, setSelectedLang] = useState<SupportedLanguage>(lang);

  const handleLanguageChange = useCallback(async (code: SupportedLanguage) => {
    setSelectedLang(code);
    await i18n.changeLanguage(code);
    setApiLocale(code);
  }, [i18n]);

  const [heroIndex, setHeroIndex] = useState(0);
  const heroScrollRef = useRef<ScrollView>(null);

  // Auto-scroll hero every 4s
  useEffect(() => {
    const timer = setInterval(() => {
      setHeroIndex((prev) => {
        const next = (prev + 1) % HERO_SLIDES.length;
        heroScrollRef.current?.scrollTo({ x: next * HERO_WIDTH, animated: true });
        return next;
      });
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <View style={{ flex: 1, backgroundColor: '#F4FBF6' }}>
      <SafeAreaView style={{ flex: 1 }} edges={['top']}>
        <ScrollView contentContainerStyle={{ paddingBottom: 32 }} showsVerticalScrollIndicator={false}>

          {/* ── Header: Logo + Language selector ── */}
          <View style={pubStyles.headerRow}>
            <Image source={APP_LOGO} style={pubStyles.logo} contentFit="contain" cachePolicy="memory-disk" />
            <View style={pubStyles.langRow}>
              {LANGUAGES.map((l) => (
                <Pressable
                  key={l.code}
                  onPress={() => handleLanguageChange(l.code)}
                  style={[
                    pubStyles.langPill,
                    selectedLang === l.code && { backgroundColor: colors.primary, borderColor: colors.primary },
                  ]}
                >
                  <Text style={{ fontSize: 13 }}>{l.flag}</Text>
                  <Text style={{
                    fontSize: 11, fontWeight: '600', marginLeft: 3,
                    color: selectedLang === l.code ? '#fff' : colors.onSurfaceVariant,
                  }}>
                    {l.label}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          {/* ── Hero slider — ScrollView horizontal ── */}
          <View style={{ paddingHorizontal: 16, paddingTop: 8 }}>
            <ScrollView
              ref={heroScrollRef}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              snapToInterval={HERO_WIDTH}
              decelerationRate="fast"
              onMomentumScrollEnd={(e) => {
                const idx = Math.round(e.nativeEvent.contentOffset.x / HERO_WIDTH);
                setHeroIndex(idx);
              }}
            >
              {HERO_SLIDES.map((item, i) => item.isLogo ? (
                <View key={i} style={[pubStyles.heroSlideLogo, { width: HERO_WIDTH }]}>
                  <Image source={APP_LOGO} style={pubStyles.heroLogoBig} contentFit="contain" cachePolicy="memory-disk" />
                  <Text style={pubStyles.heroLogoTitle}>
                    {t(`home.hero.${item.titleKey}`)}
                  </Text>
                  <Text style={pubStyles.heroLogoDesc}>
                    {t(`home.hero.${item.descKey}`)}
                  </Text>
                </View>
              ) : (
                <View key={i} style={[pubStyles.heroSlide, { width: HERO_WIDTH, backgroundColor: item.bgColor }]}>
                  <View style={[pubStyles.heroBgCircle1, { backgroundColor: item.bgEnd }]} />
                  <View style={[pubStyles.heroBgCircle2, { borderColor: 'rgba(255,255,255,0.1)' }]} />
                  <View style={pubStyles.heroMainCircle}>
                    <MaterialCommunityIcons name={item.mainIcon as keyof typeof MaterialCommunityIcons.glyphMap} size={48} color="#fff" />
                    {item.badge && (
                      <View style={pubStyles.heroBadge}>
                        <Text style={pubStyles.heroBadgeText}>{item.badge}</Text>
                      </View>
                    )}
                  </View>
                  <View style={pubStyles.heroTextBlock}>
                    <Text style={pubStyles.heroTitle}>
                      {t(`home.hero.${item.titleKey}`)}
                    </Text>
                    <Text style={pubStyles.heroDesc}>
                      {t(`home.hero.${item.descKey}`)}
                    </Text>
                    {item.smallIcons && (
                      <View style={pubStyles.heroMiniIcons}>
                        {item.smallIcons.map((si, idx) => (
                          <View key={idx} style={pubStyles.heroMiniCircle}>
                            <MaterialCommunityIcons name={si as keyof typeof MaterialCommunityIcons.glyphMap} size={14} color="#fff" />
                          </View>
                        ))}
                      </View>
                    )}
                  </View>
                </View>
              ))}
            </ScrollView>
            {/* Dots */}
            <View style={pubStyles.heroDots}>
              {HERO_SLIDES.map((slide, i) => (
                <View
                  key={i}
                  style={[
                    pubStyles.heroDot,
                    { backgroundColor: i === heroIndex ? slide.bgColor : '#D0D0D0', width: i === heroIndex ? 20 : 8 },
                  ]}
                />
              ))}
            </View>
          </View>

          {/* ── Quick actions 2×2 grid ── */}
          <View style={pubStyles.actionsGrid}>
            {[0, 2].map((rowStart) => (
              <View key={rowStart} style={pubStyles.actionsRow2}>
                {QUICK_ACTIONS.slice(rowStart, rowStart + 2).map((item) => (
                  <Pressable
                    key={item.labelKey}
                    style={[pubStyles.actionCard, { backgroundColor: item.bg + 'CC' }]}
                    onPress={() => router.push(QUICK_ACTION_ROUTES[item.labelKey] as any)}
                    android_ripple={{ color: item.color + '30' }}
                  >
                    <View style={pubStyles.actionCircle}>
                      <MaterialCommunityIcons name={item.icon} size={28} color={item.color} />
                    </View>
                    <Text style={[pubStyles.actionLabel, { color: item.color }]}>
                      {t(`home.quickActions.${item.labelKey}`)}
                    </Text>
                    <Text style={{ fontSize: 10, color: item.color, opacity: 0.7, marginTop: 2 }}>
                      {t(`home.quickActions.${item.labelKey}Desc`)}
                    </Text>
                  </Pressable>
                ))}
              </View>
            ))}
          </View>

          {/* ── AI Chat card ── */}
          <View style={{ paddingHorizontal: 16, paddingTop: 4 }}>
            <Pressable
              style={[pubStyles.chatCard, { backgroundColor: colors.primaryContainer }]}
              onPress={() => router.push('/(tabs)/chat')}
              android_ripple={{ color: colors.primary + '20' }}
            >
              <View style={[pubStyles.chatIconCircle, { backgroundColor: colors.primary }]}>
                <MaterialCommunityIcons name="star-four-points" size={22} color={colors.onPrimary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text variant="titleSmall" style={{ color: colors.onPrimaryContainer, fontWeight: '600' }}>
                  {t('chat.title')}
                </Text>
                <Text variant="bodySmall" style={{ color: colors.onPrimaryContainer, opacity: 0.8 }}>
                  {lang === 'fr' ? 'Posez vos questions sur les démarches' :
                   lang === 'en' ? 'Ask about any procedure' :
                   'Pregunta sobre cualquier trámite'}
                </Text>
              </View>
              <MaterialCommunityIcons name="chevron-right" size={24} color={colors.onPrimaryContainer} />
            </Pressable>
          </View>

          {/* ── Auth CTA — full width, native Android ── */}
          <View style={pubStyles.authSection}>
            <Pressable
              onPress={() => router.push('/(auth)/sign-up')}
              style={[pubStyles.authBtnPrimary, { backgroundColor: colors.primary }]}
              android_ripple={{ color: 'rgba(255,255,255,0.25)' }}
            >
              <Text style={pubStyles.authBtnPrimaryText}>{t('auth.signUp')}</Text>
            </Pressable>
            <Pressable
              onPress={() => router.push('/(auth)/sign-in')}
              style={[pubStyles.authBtnOutline, { borderColor: colors.primary }]}
              android_ripple={{ color: colors.primaryContainer }}
            >
              <Text style={[pubStyles.authBtnOutlineText, { color: colors.primary }]}>{t('auth.signIn')}</Text>
            </Pressable>
          </View>

        </ScrollView>
      </SafeAreaView>
    </View>
  );
}

const pubStyles = StyleSheet.create({
  // Header: logo left, lang right
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 4,
  },
  logo: {
    width: 100,
    height: 32,
  },
  langRow: {
    flexDirection: 'row',
    gap: 5,
  },
  langPill: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 8, paddingVertical: 4,
    borderRadius: 14, borderWidth: 1, borderColor: '#D0D0D0',
  },

  // Hero slider
  heroSlideLogo: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 20,
    padding: 24,
    minHeight: 190,
    backgroundColor: '#FFFFFF',
    borderWidth: 2.5,
    borderColor: '#0D6E3F',
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 6,
  },
  heroLogoBig: {
    width: 140, height: 48,
  },
  heroLogoTitle: {
    fontSize: 17, fontWeight: '700', color: '#0D6E3F',
    marginTop: 14, textAlign: 'center', lineHeight: 22,
  },
  heroLogoDesc: {
    fontSize: 12, color: '#666',
    marginTop: 6, textAlign: 'center',
  },
  heroSlide: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 20,
    padding: 22,
    minHeight: 190,
    overflow: 'hidden',
  },
  heroBgCircle1: {
    position: 'absolute', top: -30, right: -30,
    width: 120, height: 120, borderRadius: 60, opacity: 0.3,
  },
  heroBgCircle2: {
    position: 'absolute', bottom: -20, left: -15,
    width: 80, height: 80, borderRadius: 40,
    borderWidth: 2, backgroundColor: 'transparent',
  },
  heroMainCircle: {
    width: 88, height: 88, borderRadius: 44,
    backgroundColor: 'rgba(255,255,255,0.18)',
    justifyContent: 'center', alignItems: 'center',
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.25)',
  },
  heroBadge: {
    position: 'absolute', bottom: -4, right: -4,
    backgroundColor: '#FFD600',
    paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 10, elevation: 2,
  },
  heroBadgeText: {
    fontSize: 10, fontWeight: '800', color: '#333',
  },
  heroTextBlock: {
    flex: 1, marginLeft: 16,
  },
  heroTitle: {
    color: '#fff',
    fontSize: 19,
    fontWeight: '800',
    lineHeight: 24,
  },
  heroDesc: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 12,
    marginTop: 5,
    lineHeight: 17,
  },
  heroMiniIcons: {
    flexDirection: 'row', gap: 6, marginTop: 10,
  },
  heroMiniCircle: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.15)',
    justifyContent: 'center', alignItems: 'center',
  },
  heroDots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 5,
    marginTop: 10,
    marginBottom: 6,
  },
  heroDot: {
    height: 6,
    borderRadius: 3,
  },

  // Quick actions 2×2
  actionsGrid: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 12,
    gap: 10,
  },
  actionsRow2: {
    flexDirection: 'row',
    gap: 10,
  },
  actionCard: {
    flex: 1,
    alignItems: 'center',
    borderRadius: 14,
    borderWidth: 2,
    borderColor: 'rgba(0,0,0,0.06)',
    paddingVertical: 16,
    paddingHorizontal: 10,
  },
  actionCircle: {
    width: 48,
    height: 48,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  actionLabel: {
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },

  // Chat card
  chatCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 16,
    padding: 16,
    gap: 14,
  },
  chatIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },

  // Auth buttons
  authSection: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 16,
    gap: 10,
  },
  authBtnPrimary: {
    flex: 1,
    height: 50,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 2,
  },
  authBtnPrimaryText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  authBtnOutline: {
    flex: 1,
    height: 50,
    borderRadius: 12,
    borderWidth: 1.5,
    justifyContent: 'center',
    alignItems: 'center',
  },
  authBtnOutlineText: {
    fontSize: 15,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
});

// ---------------------------------------------------------------------------
// Auth Dashboard
// ---------------------------------------------------------------------------

function AuthDashboard() {
  const router = useRouter();
  const { t } = useTranslation();
  const { colors, spacing } = useAppTheme();
  const { user } = useAuth();
  // Cold-start gate: while React Query is rehydrating its MMKV-backed cache
  // we render a skeleton instead of letting `isLoading` flip to true and
  // trigger redundant fetches (the cache is being delivered any moment now).
  const isRestoring = useIsRestoring();

  const { data, isLoading, refetch, isRefetching } = useDashboard(!!user);
  const [activeTab, setActiveTab] = useState<TabValue>('requests');

  const firstName = user ? getFullName(user).split(' ')[0] : '';

  const onRefresh = useCallback(() => { refetch(); }, [refetch]);

  if (isRestoring || isLoading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
        <FullScreenSkeleton rows={6} />
      </SafeAreaView>
    );
  }

  if (!data) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
        <ScrollView
          contentContainerStyle={[styles.emptyContainer, { padding: spacing.lg }]}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={onRefresh} colors={[colors.primary]} />}
        >
          <MaterialCommunityIcons name="file-document-outline" size={64} color={colors.outlineVariant} />
          <Text variant="titleMedium" style={{ color: colors.onSurfaceVariant, marginTop: spacing.md, fontWeight: '600' }}>
            {t('dashboard.noRequests')}
          </Text>
          <Button mode="contained" onPress={() => router.push('/wizard/select-workflow' as never)} style={{ marginTop: spacing.lg }} icon="plus">
            {t('dashboard.quickActions.newRequest')}
          </Button>
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      {/* ═══ APP HEADER (dashboard only) ═══ */}
      <View style={[styles.appHeader, { backgroundColor: colors.surface }]}>
        <View style={styles.headerRow}>
          <Image source={APP_LOGO} style={styles.headerLogo} contentFit="contain" cachePolicy="memory-disk" />
          <NotificationBellButton color={colors.onSurface} />
        </View>
        <View style={[styles.headerLine, { backgroundColor: colors.primary }]} />
      </View>

      <ScrollView
        contentContainerStyle={{ paddingBottom: 24 }}
        refreshControl={
          <RefreshControl refreshing={isRefetching} onRefresh={onRefresh} colors={[colors.primary]} tintColor={colors.primary} />
        }
      >
        {/* Greeting */}
        <View style={{ paddingHorizontal: spacing.md, paddingTop: 10, paddingBottom: 8 }}>
          <Text variant="titleMedium" style={{ color: colors.onBackground, fontWeight: '700' }}>
            {t('dashboard.greeting', { name: firstName })}
          </Text>
        </View>

        {/* Compact Stats Strip */}
        <View style={{ paddingHorizontal: spacing.md, marginBottom: 8 }}>
          <CompactStats stats={data.stats} colors={colors} t={t} />
        </View>

        {/* Urgent Notifications (inline, not card) */}
        {data.action_required.length > 0 && (
          <View style={{ paddingHorizontal: spacing.md, marginBottom: 8 }}>
            <UrgentNotifications actions={data.action_required} colors={colors} router={router} />
          </View>
        )}

        {/* Upcoming Appointment */}
        {data.upcoming_appointment && (
          <View style={{ paddingHorizontal: spacing.md, marginBottom: 8 }}>
            <AppointmentCard appointment={data.upcoming_appointment} />
          </View>
        )}

        {/* Quick Actions */}
        <View style={{ paddingHorizontal: spacing.md, marginBottom: 12 }}>
          <QuickActions />
        </View>

        <Divider />

        {/* Tabs */}
        <View style={{ paddingHorizontal: spacing.md, paddingTop: 8, marginBottom: spacing.sm }}>
          <SegmentedButtons
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as TabValue)}
            buttons={[
              { value: 'requests', label: t('dashboard.tabs.requests'), icon: 'file-document-outline' },
              { value: 'payments', label: t('dashboard.tabs.payments'), icon: 'cash' },
              { value: 'notifications', label: t('dashboard.tabs.notifications'), icon: 'bell-outline', showSelectedCheck: false },
            ]}
            density="small"
          />
        </View>

        {/* Tab Content */}
        <View style={{ marginHorizontal: spacing.md }}>
          {activeTab === 'requests' && <RecentRequestsList requests={data.recent_requests} />}
          {activeTab === 'payments' && <RecentPaymentsList payments={data.recent_payments} />}
          {activeTab === 'notifications' && <NotificationsList notifications={data.notifications} />}
        </View>

        {activeTab === 'requests' && data.recent_requests.length > 0 && (
          <Button
            mode="text"
            onPress={() => router.push('/(tabs)/requests')}
            style={{ marginTop: 4 }}
            icon="arrow-right"
            contentStyle={{ flexDirection: 'row-reverse' }}
          >
            {t('common.seeAll')}
          </Button>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  emptyContainer: { flexGrow: 1, justifyContent: 'center', alignItems: 'center' },

  // App header
  appHeader: { paddingHorizontal: 16, paddingTop: 8, paddingBottom: 0 },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  headerLogo: { height: 28, width: 100 },
  headerLine: { height: 1.5, marginTop: 8 },

  // Compact stats
  statsStrip: { flexDirection: 'row', backgroundColor: '#FAFAFA', borderRadius: 8, overflow: 'hidden' },
  statItem: { flex: 1, alignItems: 'center', paddingVertical: 10, paddingHorizontal: 4 },
  statItemBorder: { borderRightWidth: 1, borderRightColor: '#E0E0E0' },
  statValue: { fontSize: 18, fontWeight: '700' },
  statLabel: { fontSize: 10, marginTop: 2, textAlign: 'center' },

  // Urgent notifications
  urgentItem: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, paddingHorizontal: 8, borderLeftWidth: 3, backgroundColor: '#FFF3E0', borderRadius: 4, marginBottom: 4 },
});

// ---------------------------------------------------------------------------
// Export: Conditional render based on auth state
// ---------------------------------------------------------------------------

export default function HomeScreen() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AuthDashboard /> : <PublicHome />;
}
