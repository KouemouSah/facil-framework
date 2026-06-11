/**
 * Account Tab — Login/Register CTA (public mode only)
 *
 * Shown only when user is NOT authenticated.
 * Hidden via href:null when authenticated (replaced by Profile tab).
 */

import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Text, Button } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';

const APP_LOGO = require('../../../assets/images/icon_facil.png');

const BENEFITS = [
  { icon: 'file-document-edit-outline' as const, key: 'requests' },
  { icon: 'credit-card-outline' as const, key: 'payments' },
  { icon: 'calendar-check' as const, key: 'appointments' },
  { icon: 'bell-ring-outline' as const, key: 'tracking' },
] as const;

const BENEFIT_LABELS: Record<string, Record<string, string>> = {
  requests: { es: 'Iniciar solicitudes de servicio', fr: 'Soumettre des demandes de service', en: 'Submit service requests' },
  payments: { es: 'Realizar pagos en línea', fr: 'Effectuer des paiements en ligne', en: 'Make online payments' },
  appointments: { es: 'Agendar citas', fr: 'Prendre des rendez-vous', en: 'Schedule appointments' },
  tracking: { es: 'Seguimiento de trámites', fr: 'Suivi de vos démarches', en: 'Track your procedures' },
};

export default function AccountScreen() {
  const { colors } = useAppTheme();
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const lang = (i18n.language || 'es') as 'es' | 'fr' | 'en';

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.background }]}>
      <View style={s.content}>
        {/* Logo */}
        <Image source={APP_LOGO} style={s.logo} contentFit="contain" cachePolicy="memory-disk" />

        {/* Title */}
        <Text variant="headlineSmall" style={{ fontWeight: '600', color: colors.onSurface, marginTop: 20 }}>
          {lang === 'fr' ? 'Bienvenue sur Facil' : lang === 'en' ? 'Welcome to Facil' : 'Bienvenido a Facil'}
        </Text>
        <Text variant="bodyMedium" style={{ color: colors.onSurfaceVariant, textAlign: 'center', marginTop: 4 }}>
          {lang === 'fr' ? 'Créez un compte pour gérer vos démarches' :
           lang === 'en' ? 'Create an account to manage your procedures' :
           'Crea una cuenta para gestionar tus trámites'}
        </Text>

        {/* Benefits */}
        <View style={s.benefits}>
          {BENEFITS.map((b) => (
            <View key={b.key} style={s.benefitRow}>
              <MaterialCommunityIcons name={b.icon} size={22} color={colors.primary} />
              <Text variant="bodyMedium" style={{ color: colors.onSurface, flex: 1, marginLeft: 14 }}>
                {BENEFIT_LABELS[b.key]?.[lang] ?? b.key}
              </Text>
            </View>
          ))}
        </View>

        {/* Actions */}
        <View style={s.actions}>
          <Button
            mode="contained"
            onPress={() => router.push('/(auth)/sign-in')}
            contentStyle={{ height: 48 }}
            style={{ width: '100%' }}
          >
            {t('auth.signIn')}
          </Button>
          <Button
            mode="text"
            onPress={() => router.push('/(auth)/sign-up')}
            textColor={colors.primary}
          >
            {t('auth.signUp')}
          </Button>
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 32,
  },
  logo: { width: 72, height: 72, borderRadius: 36 },
  benefits: {
    width: '100%',
    marginTop: 28,
    gap: 16,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  actions: {
    width: '100%',
    marginTop: 32,
    gap: 8,
    alignItems: 'center',
  },
});
