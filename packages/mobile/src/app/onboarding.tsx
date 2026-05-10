/**
 * Onboarding — First launch only
 *
 * Design: Split layout inspired by modern app onboarding
 * - Top 55%: vibrant color background + large Lottie animation
 * - Bottom 45%: white card with title, subtitle, description
 * - Each slide has unique accent color
 * - Responsive: uses % heights for all screen sizes
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  StyleSheet,
  View,
  FlatList,
  useWindowDimensions,
  Pressable,
  Image,
  Animated,
  Easing,
  type ViewToken,
} from 'react-native';
import { Text, Button } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import LottieView from 'lottie-react-native';

import { storage } from '@core/storage/mmkv';

const ONBOARDING_KEY = 'onboarding_completed';
const TOP_RATIO = 0.52;
/** Vertical padding reserved at the bottom of the white card for the absolute
 *  controls overlay. The last slide stacks: explore button (~40dp) + auth
 *  buttons row (~46dp) + dots (~14dp) + safe-area inset + paddingBottom 8.
 *  Bumping a touch generously to absorb i18n font-scaling. */
const CONTROLS_HEIGHT_LAST = 180;
const CONTROLS_HEIGHT_DEFAULT = 100;

// ---------------------------------------------------------------------------
// Slide config
// ---------------------------------------------------------------------------

interface Slide {
  id: string;
   
  animation?: any;
  icon?: string;
  titleKey: string;
  descSubKey: string;
  descKey: string;
  bgTop: string;
  bgTopEnd: string;
  accent: string;
  decoIcons?: string[];
  watermarkIcon?: string;
  useCloudBg?: boolean;
  titleSameSize?: boolean;
  useWordCloud?: boolean;
  noWatermark?: boolean;
  lottieCentered?: boolean;
  titleBigScale?: number;
}

const SLIDES: Slide[] = [
  {
    id: '1',
    animation: require('../../assets/animations/robot.json'),
    titleKey: 'onboarding.slide1.title',
    descSubKey: 'onboarding.slide1.desc_sub',
    descKey: 'onboarding.slide1.desc',
    bgTop: '#0D6E3F',
    bgTopEnd: '#1B9E5A',
    accent: '#0D6E3F',
    lottieCentered: true,
    decoIcons: ['passport', 'car', 'file-document-outline', 'home-city-outline', 'account-group-outline'],
  },
  {
    id: '2',
    animation: require('../../assets/animations/chatbot.json'),
    titleKey: 'onboarding.slide2.title',
    descSubKey: 'onboarding.slide2.desc_sub',
    descKey: 'onboarding.slide2.desc',
    bgTop: '#B71C1C',
    bgTopEnd: '#E53935',
    accent: '#B71C1C',
    watermarkIcon: 'shield-lock',
    useCloudBg: true,
    titleSameSize: true,
  },
  {
    id: '3',
    icon: 'rocket-launch-outline',
    titleKey: 'onboarding.slide3.title',
    descSubKey: 'onboarding.slide3.desc_sub',
    descKey: 'onboarding.slide3.desc',
    bgTop: '#E65100',
    bgTopEnd: '#FF8A65',
    accent: '#E65100',
    useWordCloud: true,
    noWatermark: true,
    titleBigScale: 0.7,
  },
];

// Word cloud — terms describing the app, scattered at various sizes/positions
const WORD_CLOUD = [
  { text: 'Passeport', size: 30, top: '5%', left: '5%', rotate: '-8deg' },
  { text: 'Résidence', size: 34, top: '12%', right: '8%', rotate: '5deg' },
  { text: 'Véhicules', size: 38, top: '8%', left: '42%', rotate: '-3deg' },
  { text: 'Contrats', size: 42, top: '20%', left: '3%', rotate: '6deg' },
  { text: 'IA', size: 54, top: '18%', right: '18%', rotate: '-10deg' },
  { text: 'Licences', size: 32, top: '30%', left: '8%', rotate: '4deg' },
  { text: '2FA', size: 36, top: '26%', right: '5%', rotate: '-6deg' },
  { text: 'Paiements', size: 46, top: '38%', left: '2%', rotate: '-4deg' },
  { text: 'Sécurité', size: 40, top: '35%', right: '8%', rotate: '8deg' },
  { text: 'Digital', size: 56, top: '48%', left: '5%', rotate: '-5deg' },
  { text: 'Rapide', size: 34, top: '45%', right: '3%', rotate: '3deg' },
  { text: 'Trilingue', size: 38, top: '55%', left: '8%', rotate: '7deg' },
  { text: 'OCR', size: 30, top: '52%', right: '15%', rotate: '-9deg' },
  { text: 'Suivi', size: 44, top: '62%', right: '5%', rotate: '4deg' },
  { text: 'Facil', size: 62, top: '60%', left: '3%', rotate: '-3deg' },
  { text: 'RDV', size: 32, top: '70%', left: '25%', rotate: '6deg' },
  { text: 'PDF', size: 36, top: '68%', right: '8%', rotate: '-7deg' },
  { text: 'Trámites', size: 50, top: '75%', left: '5%', rotate: '2deg' },
  { text: 'Chat', size: 34, top: '78%', right: '20%', rotate: '-4deg' },
  { text: 'Mobile', size: 42, top: '15%', left: '25%', rotate: '9deg' },
];

// LANGUAGES picker removed from the last slide (overlapped the bottom
// controls on small phones with i18n-stretched labels). Locale change
// stays available through Profile → Preferences once authenticated, and
// i18next still falls back to the device's system locale by default.

// ---------------------------------------------------------------------------
// Animated border circle — blinking border around children
// ---------------------------------------------------------------------------

function AnimatedBorderCircle({ size, color, children }: { size: number; color: string; children: React.ReactNode }) {
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.15, duration: 1000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: 1000, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    ).start();
  }, []);

  return (
    <View style={{ width: size, height: size, justifyContent: 'center', alignItems: 'center' }}>
      <Animated.View
        style={{
          position: 'absolute',
          width: size,
          height: size,
          borderRadius: size / 2,
          borderWidth: 2.5,
          borderColor: color,
          opacity,
        }}
      />
      {children}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Animated rocket icon — pulse scale + gentle float
// ---------------------------------------------------------------------------

function AnimatedRocketIcon({ size, iconName }: { size: number; iconName: string }) {
  const scale = useRef(new Animated.Value(1)).current;
  const translateY = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Pulse scale
    Animated.loop(
      Animated.sequence([
        Animated.timing(scale, { toValue: 1.08, duration: 1200, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(scale, { toValue: 1, duration: 1200, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    ).start();
    // Float up/down
    Animated.loop(
      Animated.sequence([
        Animated.timing(translateY, { toValue: -8, duration: 1600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(translateY, { toValue: 8, duration: 1600, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
      ]),
    ).start();
  }, []);

  return (
    <Animated.View style={[s.iconCircleLarge, { transform: [{ scale }, { translateY }] }]}>
      <MaterialCommunityIcons
        name={iconName as keyof typeof MaterialCommunityIcons.glyphMap}
        size={size * 0.45}
        color="#fff"
      />
    </Animated.View>
  );
}

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function OnboardingScreen() {
  const router = useRouter();
  const { t } = useTranslation();
  // Reactive dimensions — survives device rotation and split-screen better
  // than the cached Dimensions.get('window') we used to call at module-load.
  const { width: SW, height: SH } = useWindowDimensions();

  const [currentIndex, setCurrentIndex] = useState(0);
  const flatListRef = useRef<FlatList>(null);
  const isLastSlide = currentIndex === SLIDES.length - 1;

  const handleNext = useCallback(() => {
    if (isLastSlide) {
      completeOnboarding();
    } else {
      flatListRef.current?.scrollToIndex({ index: currentIndex + 1, animated: true });
    }
  }, [currentIndex, isLastSlide]);

  const handleSkip = useCallback(() => completeOnboarding(), []);

  const completeOnboarding = useCallback(() => {
    storage.set(ONBOARDING_KEY, true);
    router.replace('/' as never);
  }, [router]);

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0 && viewableItems[0].index != null) {
        setCurrentIndex(viewableItems[0].index);
      }
    },
  ).current;

  const viewabilityConfig = useRef({ viewAreaCoveragePercentThreshold: 50 }).current;

  // ---------------------------------------------------------------------------
  // Render slide
  // ---------------------------------------------------------------------------

  const renderSlide = ({ item, index }: { item: Slide; index: number }) => {
    const titleText = t(item.titleKey);
    const parts = titleText.split('\n');

    return (
      <View style={[s.slide, { width: SW }]}>
        {/* ═══ TOP: colored bg + animation + deco ═══ */}
        <View style={[s.topSection, { height: SH * TOP_RATIO, backgroundColor: item.bgTop }]}>
          {/* Futuristic lines */}
          <View style={[s.futureLine, { top: '15%', transform: [{ rotate: '-8deg' }], backgroundColor: 'rgba(255,255,255,0.08)' }]} />
          <View style={[s.futureLine, { top: '55%', transform: [{ rotate: '-3deg' }], backgroundColor: 'rgba(255,255,255,0.07)' }]} />
          <View style={[s.futureCircle, { top: '8%', right: -30, backgroundColor: 'rgba(255,255,255,0.05)' }]} />

          {/* Background decoration: word cloud, clouds, or icon cloud */}
          {item.useWordCloud ? (
            <>
              {/* Word cloud — scattered text labels */}
              {WORD_CLOUD.map((w, i) => (
                <Text
                  key={`wc-${i}`}
                  style={{
                    position: 'absolute',
                    fontSize: w.size,
                    fontWeight: w.size >= 20 ? '800' : w.size >= 16 ? '600' : '400',
                    color: '#fff',
                    opacity: 0.12 + (w.size - 30) * 0.003,
                    top: w.top as any,
                    left: (w as any).left,
                    right: (w as any).right,
                    transform: [{ rotate: w.rotate }],
                  }}
                >
                  {w.text}
                </Text>
              ))}
            </>
          ) : item.useCloudBg ? (
            <>
              {/* Large overlapping cloud shapes — varied sizes, spread across */}
              <View style={[s.cloudShape, { top: '2%', left: '-8%', width: 200, height: 75 }]} />
              <View style={[s.cloudShape, { top: '18%', right: '-5%', width: 250, height: 90 }]} />
              <View style={[s.cloudShape, { top: '10%', left: '30%', width: 160, height: 60 }]} />
              <View style={[s.cloudShape, { top: '35%', left: '-5%', width: 190, height: 72 }]} />
              <View style={[s.cloudShape, { top: '50%', right: '2%', width: 220, height: 82 }]} />
              <View style={[s.cloudShape, { top: '65%', left: '8%', width: 180, height: 68 }]} />
              <View style={[s.cloudShape, { top: '28%', right: '20%', width: 140, height: 55 }]} />
              <View style={[s.cloudShape, { top: '75%', right: '-3%', width: 200, height: 75 }]} />
              <View style={[s.cloudShape, { top: '5%', left: '55%', width: 120, height: 48 }]} />
              <View style={[s.cloudShape, { top: '58%', left: '35%', width: 150, height: 58 }]} />
              {/* Small floating clouds */}
              <View style={[s.cloudShapeSmall, { top: '8%', right: '15%' }]} />
              <View style={[s.cloudShapeSmall, { top: '42%', left: '3%' }]} />
              <View style={[s.cloudShapeSmall, { top: '80%', left: '45%' }]} />
            </>
          ) : (
            <>
              {/* Icon cloud around animation */}
              {[
                { icon: 'passport', size: 22, top: '14%', left: '18%' },
                { icon: 'car-outline', size: 16, top: '10%', right: '20%' },
                { icon: 'file-document-outline', size: 20, top: '22%', left: '10%' },
                { icon: 'shield-check-outline', size: 14, top: '18%', right: '12%' },
                { icon: 'home-city-outline', size: 18, top: '52%', left: '10%' },
                { icon: 'scale-balance', size: 24, top: '56%', right: '14%' },
                { icon: 'calculator-variant-outline', size: 12, top: '65%', left: '20%' },
                { icon: 'translate', size: 16, top: '62%', right: '18%' },
                { icon: 'cellphone', size: 14, top: '35%', left: '6%' },
                { icon: 'earth', size: 18, top: '42%', right: '6%' },
                { icon: 'fingerprint', size: 12, top: '28%', left: '22%' },
                { icon: 'account-outline', size: 16, top: '70%', right: '26%' },
              ].map((ic, i) => (
                <MaterialCommunityIcons
                  key={`ic-${i}`}
                  name={ic.icon as keyof typeof MaterialCommunityIcons.glyphMap}
                  size={ic.size}
                  color="#fff"
                  style={{
                    position: 'absolute',
                    opacity: 0.18,
                    top: ic.top as any,
                    left: (ic as any).left,
                    right: (ic as any).right,
                  }}
                />
              ))}
              {/* Circles of different sizes */}
              <View style={[s.decoCircle, { top: '6%', left: '30%', width: 50, height: 50, borderRadius: 25 }]} />
              <View style={[s.decoCircle, { top: '16%', right: '5%', width: 30, height: 30, borderRadius: 15 }]} />
              <View style={[s.decoCircle, { top: '48%', left: '3%', width: 20, height: 20, borderRadius: 10 }]} />
              <View style={[s.decoCircle, { top: '60%', right: '2%', width: 40, height: 40, borderRadius: 20 }]} />
              <View style={[s.decoCircle, { top: '75%', left: '35%', width: 14, height: 14, borderRadius: 7 }]} />
              <View style={[s.decoCircle, { top: '8%', right: '35%', width: 10, height: 10, borderRadius: 5 }]} />
              <View style={[s.decoCircle, { top: '68%', left: '8%', width: 24, height: 24, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.08)' }]} />
              {/* Small clouds */}
              <View style={[s.cloud, { top: '12%', left: '45%', width: 36, height: 14 }]} />
              <View style={[s.cloud, { top: '70%', right: '35%', width: 28, height: 12 }]} />
            </>
          )}

          {/* Animation or animated icon */}
          {item.animation ? (
            item.lottieCentered ? (
              <View style={s.rocketCenter}>
                <AnimatedBorderCircle size={SW * 0.55} color="rgba(255,255,255,0.5)">
                  <LottieView
                    source={item.animation}
                    autoPlay
                    loop
                    style={[s.lottieCentered, { width: SW * 0.75, height: SW * 0.75 }]}
                  />
                </AnimatedBorderCircle>
              </View>
            ) : (
              <LottieView
                source={item.animation}
                autoPlay
                loop
                style={[s.lottie, { width: SW * 0.98, height: SW * 0.98 }]}
              />
            )
          ) : item.icon ? (
            <View style={s.rocketCenter}>
              <AnimatedRocketIcon size={300} iconName={item.icon} />
            </View>
          ) : null}

          {/* Curved bottom edge */}
          <View style={s.curveOverlay} />
        </View>

        {/* ═══ BOTTOM: white card with text + watermark ═══
            The absolute controls overlay sits on top of this card; we reserve
            CONTROLS_HEIGHT_* at the bottom so the inner content (subtitle /
            description / language picker) never slips under the buttons. */}
        <View
          style={[
            s.bottomSection,
            {
              paddingBottom:
                index === SLIDES.length - 1
                  ? CONTROLS_HEIGHT_LAST
                  : CONTROLS_HEIGHT_DEFAULT,
            },
          ]}
        >
          {/* Watermark: icon, image, or none */}
          {item.noWatermark ? null : item.watermarkIcon ? (
            <View style={s.watermarkIconWrap}>
              <MaterialCommunityIcons
                name={item.watermarkIcon as keyof typeof MaterialCommunityIcons.glyphMap}
                size={360}
                color={item.accent}
                style={{ opacity: 0.04 }}
              />
            </View>
          ) : (
            <View style={s.watermarkWrap}>
              <Image
                source={require('../../assets/images/icon_facil_watermark.png')}
                style={s.watermarkImg}
                resizeMode="contain"
              />
              <View style={[s.splashRect, { top: 0, right: 0, width: '45%', height: '35%' }]} />
              <View style={[s.splashRect, { bottom: 0, left: '15%', width: '55%', height: '30%', borderTopLeftRadius: 50 }]} />
              <View style={[s.splashCircle, { top: '25%', right: '5%', backgroundColor: `${item.accent}0A` }]} />
            </View>
          )}

          {/* Title */}
          <View style={{ zIndex: 2 }}>
            {item.titleSameSize ? (
              /* Line 1 big, Line 2: small connector + big word */
              <>
                {parts[0] && (
                  <Text
                    style={[s.titleUniform, { color: item.accent }]}
                    numberOfLines={1}
                    adjustsFontSizeToFit
                    minimumFontScale={0.55}
                  >
                    {parts[0]}
                  </Text>
                )}
                {parts[1] && (
                  <Text style={{ lineHeight: 80 }} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.55}>
                    {/* Split "et Sécurisé" → "et" small + "Sécurisé" big */}
                    <Text style={{ fontSize: 39, fontWeight: '400', color: item.accent, opacity: 0.6 }}>
                      {parts[1].split(' ')[0]}{' '}
                    </Text>
                    <Text style={[s.titleUniform, { color: item.accent }]}>
                      {parts[1].split(' ').slice(1).join(' ')}
                    </Text>
                  </Text>
                )}
              </>
            ) : (
              /* Default: small line + BIG line (with optional scale).
                 `adjustsFontSizeToFit` + `numberOfLines={1}` so long words like
                 "Maintenant" / "Inmediatamente" gracefully shrink to fit one
                 line instead of wrapping mid-word and overlapping the bottom
                 controls. */
              <>
                {parts[0] && (
                  <Text style={[s.titleSmall, { color: item.accent }]} numberOfLines={1} adjustsFontSizeToFit>
                    {parts[0]}
                  </Text>
                )}
                {parts[1] && (
                  <Text
                    numberOfLines={1}
                    adjustsFontSizeToFit
                    minimumFontScale={0.5}
                    style={[
                      s.titleBig,
                      { color: item.accent },
                      item.titleBigScale ? {
                        fontSize: 100 * item.titleBigScale,
                        lineHeight: 106 * item.titleBigScale,
                        letterSpacing: 4 * item.titleBigScale,
                      } : undefined,
                    ]}
                  >
                    {parts[1]}
                  </Text>
                )}
              </>
            )}
          </View>

          {/* Subtitle */}
          <Text style={[s.subtitle, { color: item.accent, zIndex: 2 }]}>
            {t(item.descSubKey)}
          </Text>

          {/* Description */}
          <Text style={[s.desc, { zIndex: 2 }]}>
            {t(item.descKey)}
          </Text>

          {/* Language selector intentionally removed on the last slide:
              the row of three flag chips overlapped the absolute bottom
              controls (Explore / Sign-up / Sign-in / dots) on small phones
              with i18n-stretched labels. The language picker remains
              available from Profile → Preferences once the user is in the
              app, and i18next still falls back to the system locale by
              default — so no functionality is lost, only the redundant
              cluttering UI on first launch. */}
        </View>
      </View>
    );
  };

  // ---------------------------------------------------------------------------
  // Bottom controls
  // ---------------------------------------------------------------------------

  const currentSlide = SLIDES[currentIndex];

  return (
    <View style={s.container}>
      <FlatList
        ref={flatListRef}
        data={SLIDES}
        renderItem={renderSlide}
        keyExtractor={(item) => item.id}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        bounces={false}
        onViewableItemsChanged={onViewableItemsChanged}
        viewabilityConfig={viewabilityConfig}
      />

      {/* Controls overlay at bottom */}
      <SafeAreaView style={s.controls} edges={['bottom']}>
        {isLastSlide ? (
          <View style={s.lastSlideButtons}>
            {/* Explorer sans compte — above dots */}
            <Pressable
              onPress={completeOnboarding}
              style={[s.exploreBtn, { borderColor: `${currentSlide.accent}40` }]}
            >
              <Text style={{ color: currentSlide.accent, fontSize: 15, fontWeight: '600' }}>
                {t('onboarding.exploreWithout')}
              </Text>
              <MaterialCommunityIcons name="arrow-right" size={18} color={currentSlide.accent} style={{ marginLeft: 4 }} />
            </Pressable>

            {/* Auth buttons side by side — Sign Up first */}
            <View style={s.authBtnRow}>
              <Button
                mode="contained"
                onPress={() => { completeOnboarding(); router.replace('/(auth)/sign-up' as never); }}
                style={[s.authBtn, { backgroundColor: currentSlide.accent }]}
                contentStyle={{ paddingVertical: 4 }}
                labelStyle={{ fontSize: 14, fontWeight: '700' }}
              >
                {t('auth.signUp')}
              </Button>
              <Button
                mode="outlined"
                onPress={() => { completeOnboarding(); router.replace('/(auth)/sign-in' as never); }}
                style={[s.authBtn, { borderColor: currentSlide.accent }]}
                contentStyle={{ paddingVertical: 4 }}
                labelStyle={{ fontSize: 14, fontWeight: '600' }}
                textColor={currentSlide.accent}
              >
                {t('auth.signIn')}
              </Button>
            </View>

            {/* Dots */}
            <View style={s.dotsRow}>
              {SLIDES.map((_, i) => (
                <View
                  key={i}
                  style={[
                    s.dot,
                    {
                      backgroundColor: i === currentIndex ? currentSlide.accent : '#D0D0D0',
                      width: i === currentIndex ? 28 : 10,
                    },
                  ]}
                />
              ))}
            </View>
          </View>
        ) : (
          <>
            {/* Dots */}
            <View style={s.dotsRow}>
              {SLIDES.map((_, i) => (
                <View
                  key={i}
                  style={[
                    s.dot,
                    {
                      backgroundColor: i === currentIndex ? currentSlide.accent : '#D0D0D0',
                      width: i === currentIndex ? 28 : 10,
                    },
                  ]}
                />
              ))}
            </View>
            <View style={s.navRow}>
              <Pressable onPress={handleSkip} style={s.skipBtn}>
                <Text style={{ color: '#888', fontSize: 14 }}>{t('onboarding.skip')}</Text>
              </Pressable>
              <Pressable
                onPress={handleNext}
                style={[s.nextBtn, { backgroundColor: currentSlide.accent }]}
              >
                <MaterialCommunityIcons name="arrow-right" size={24} color="#fff" />
              </Pressable>
            </View>
          </>
        )}
      </SafeAreaView>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles — responsive with % and Dimensions
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  slide: { flex: 1 },

  // Top colored section — flex-end pushes Lottie to bottom (touching curve).
  // The actual height comes from the slide's inline style (computed from
  // useWindowDimensions × TOP_RATIO so rotation / split-screen update it).
  topSection: {
    justifyContent: 'flex-end',
    alignItems: 'center',
    paddingBottom: 0,
    overflow: 'hidden',
  },
  futureLine: { position: 'absolute', left: -20, right: -20, height: 2, borderRadius: 1 },
  futureCircle: { position: 'absolute', width: 80, height: 80, borderRadius: 40, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.08)' },
  cloud: { position: 'absolute', backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: 20 },
  cloudShape: { position: 'absolute', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 40 },
  cloudShapeSmall: { position: 'absolute', width: 70, height: 30, backgroundColor: 'rgba(255,255,255,0.12)', borderRadius: 15 },
  decoCircle: { position: 'absolute', borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.15)', backgroundColor: 'transparent' },
  // lottie / lottieCentered sizes are computed per-slide from
  // useWindowDimensions and applied as inline styles below. Caps via maxWidth /
  // maxHeight prevent oversize on tablets.
  lottie: { maxWidth: 448, maxHeight: 448 },
  lottieCentered: { maxWidth: 350, maxHeight: 350 },
  rocketCenter: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    justifyContent: 'center', alignItems: 'center',
  },
  iconCircleLarge: {
    width: 300, height: 300, borderRadius: 150,
    backgroundColor: 'rgba(255,255,255,0.15)',
    justifyContent: 'center', alignItems: 'center',
    borderWidth: 2, borderColor: 'rgba(255,255,255,0.2)',
  },
  curveOverlay: {
    position: 'absolute',
    bottom: -30,
    left: -20,
    right: -20,
    height: 60,
    backgroundColor: '#fff',
    borderTopLeftRadius: 40,
    borderTopRightRadius: 40,
  },

  // Bottom white section
  bottomSection: {
    flex: 1,
    backgroundColor: '#fff',
    paddingHorizontal: 28,
    paddingTop: 4,
    overflow: 'hidden',
  },
  watermarkWrap: {
    position: 'absolute', top: -100, right: -150,
    width: 500, height: 500,
    zIndex: 1,
  },
  watermarkImg: { width: 500, height: 500, opacity: 0.06 },
  watermarkIconWrap: {
    position: 'absolute', top: -40, right: -80,
    zIndex: 1,
  },
  splashRect: { position: 'absolute', backgroundColor: '#fff' },
  splashCircle: { position: 'absolute', width: 100, height: 100, borderRadius: 50 },
  titleSmall: { fontSize: 44, fontWeight: '600', letterSpacing: 0.3, marginLeft: 2 },
  titleBig: { fontSize: 100, fontWeight: '900', letterSpacing: 4, lineHeight: 106, marginBottom: 6, marginLeft: -4 },
  titleUniform: { fontSize: 72, fontWeight: '900', letterSpacing: 2, lineHeight: 80 },
  subtitle: { fontSize: 18, fontWeight: '700', opacity: 0.55, marginBottom: 12, letterSpacing: 0.5 },
  // Bottom margin separates the description ("Lancez votre première demande.")
  // from the absolute-positioned "Explorer sans compte" CTA below. The 28dp
  // margin shipped in 8a0beabf still left the dashed CTA visually glued on
  // small Android phones with FR i18n (see debug/tesoro/onboard.jpg). 36dp
  // gives audible breathing room across all 3 locales.
  desc: { fontSize: 18, lineHeight: 28, color: '#555', marginBottom: 36 },

  // Controls
  controls: {
    position: 'absolute', bottom: 0, left: 0, right: 0,
    paddingHorizontal: 28, paddingBottom: 8,
    backgroundColor: 'transparent',
  },
  dotsRow: { flexDirection: 'row', justifyContent: 'center', gap: 6, marginBottom: 16 },
  dot: { height: 8, borderRadius: 4 },

  // Nav row (non-last slides)
  navRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  skipBtn: { paddingVertical: 12, paddingHorizontal: 8 },
  nextBtn: {
    width: 56, height: 56, borderRadius: 28,
    justifyContent: 'center', alignItems: 'center',
    elevation: 4,
    shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.25, shadowRadius: 4,
  },

  // Last slide buttons — explicit paddingTop pushes the dashed "Explorer
  // sans compte" CTA away from the description text above (B1 fix
  // 2026-04-29). gap also bumped 10→12 for inter-row breathing room.
  lastSlideButtons: { gap: 12, paddingTop: 12, paddingBottom: 8 },
  authBtnRow: { flexDirection: 'row', gap: 10 },
  authBtn: { flex: 1, borderRadius: 28 },
  exploreBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    paddingVertical: 10, paddingHorizontal: 16,
    borderRadius: 28, borderWidth: 1.5, borderStyle: 'dashed',
    backgroundColor: 'rgba(230,81,0,0.04)',
  },
});
