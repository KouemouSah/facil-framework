import { useCallback, useState } from 'react';
import { View, StyleSheet, FlatList, Pressable } from 'react-native';
import { Text, Searchbar, ActivityIndicator, Button, Divider, Chip } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { useAppTheme } from '@core/theme';
import { CompanyCard } from './company-card';
import type { useBundleWizard } from '../services/bundle-hooks';

type Wizard = ReturnType<typeof useBundleWizard>;

export function CompanyIdentificationStep({ wizard, lang }: { wizard: Wizard; lang: string }) {
  const { colors } = useAppTheme();
  const [query, setQuery] = useState('');

  const handleSearch = useCallback((text: string) => {
    setQuery(text);
    wizard.searchCompany(text);
  }, [wizard]);

  const labels = {
    search: { es: 'Buscar empresa (NIF, nombre, PE-XXXX)', fr: 'Rechercher entreprise (NIF, nom, PE-XXXX)', en: 'Search company (NIF, name, PE-XXXX)' },
    myCompanies: { es: 'Mis empresas', fr: 'Mes entreprises', en: 'My companies' },
    pending: { es: 'obligaciones pendientes', fr: 'obligations en attente', en: 'pending obligations' },
    noResults: { es: 'No se encontraron empresas', fr: 'Aucune entreprise trouvée', en: 'No companies found' },
    registerNew: { es: 'Registrar nueva empresa', fr: 'Enregistrer nouvelle entreprise', en: 'Register new company' },
    registerNewDesc: {
      es: 'Suba el certificado del Padrón Empresarial para registrar automáticamente su empresa.',
      fr: "Chargez le certificat du Registre des Entreprises pour enregistrer automatiquement votre entreprise.",
      en: 'Upload the Business Registry certificate to automatically register your company.',
    },
    pay: { es: 'Pagar', fr: 'Payer', en: 'Pay' },
  } as Record<string, Record<string, string>>;
  const t = (key: string) => labels[key]?.[lang] ?? labels[key]?.es ?? key;

  if (wizard.selectedCompany) {
    return (
      <View style={{ padding: 16, gap: 12 }}>
        <CompanyCard company={wizard.selectedCompany} />
        <Button mode="outlined" onPress={wizard.clearCompanySelection}>
          {lang === 'fr' ? 'Changer' : lang === 'en' ? 'Change' : 'Cambiar'}
        </Button>
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <View style={{ padding: 16 }}>
        <Searchbar
          value={query}
          onChangeText={handleSearch}
          placeholder={t('search')}
          style={{ backgroundColor: '#EEEEEE', borderRadius: 24, elevation: 0 }}
        />
      </View>

      {/* My Companies */}
      {query.length < 2 && (
        <View>
          <Text variant="labelLarge" style={{ paddingHorizontal: 16, paddingBottom: 8, color: colors.primary }}>
            {t('myCompanies')}
          </Text>
          {wizard.isLoadingCompanies ? (
            <ActivityIndicator style={{ padding: 24 }} />
          ) : wizard.myCompanies.length === 0 ? (
            <Text variant="bodySmall" style={{ paddingHorizontal: 16, color: colors.outline }}>
              {t('noResults')}
            </Text>
          ) : (
            <FlatList
              data={wizard.myCompanies}
              keyExtractor={(item) => item.company.id}
              ItemSeparatorComponent={() => <Divider />}
              renderItem={({ item }) => (
                <Pressable
                  onPress={() => item.is_eligible && wizard.selectCompany(item.company)}
                  style={[s.row, !item.is_eligible && { opacity: 0.4 }]}
                  android_ripple={{ color: colors.primaryContainer }}
                  disabled={!item.is_eligible}
                >
                  <MaterialCommunityIcons name="domain" size={22} color={colors.primary} />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text variant="bodyMedium" style={{ fontWeight: '600' }}>{item.company.legal_name}</Text>
                    <Text variant="labelSmall" style={{ color: colors.outline }}>
                      {item.pending_obligations} {t('pending')}
                    </Text>
                  </View>
                  {item.is_eligible && (
                    <Chip compact mode="flat" textStyle={{ fontSize: 11, color: colors.primary }}>
                      {t('pay')} →
                    </Chip>
                  )}
                </Pressable>
              )}
            />
          )}

          {/* "Register new" CTA always visible below "Mes entreprises"
              (parité web CompanyIdentificationStep L150-161, m13.jpg fix
              2026-04-29). Web shows it both when the user has companies
              and when they don't — we mirror that. */}
          {!wizard.isLoadingCompanies && (
            <View style={s.registerNewBlock}>
              <Divider />
              <View style={{ paddingHorizontal: 16, paddingTop: 12 }}>
                <Button mode="outlined" onPress={wizard.requestNewCompany} icon="plus">
                  {t('registerNew')}
                </Button>
                <Text
                  variant="labelSmall"
                  style={{ color: colors.outline, textAlign: 'center', marginTop: 6 }}
                >
                  {t('registerNewDesc')}
                </Text>
              </View>
            </View>
          )}
        </View>
      )}

      {/* Search Results */}
      {query.length >= 2 && (
        <View>
          {wizard.isSearching ? (
            <ActivityIndicator style={{ padding: 24 }} />
          ) : wizard.searchResults.length === 0 ? (
            <View style={{ padding: 24, alignItems: 'center', gap: 12 }}>
              <MaterialCommunityIcons name="office-building-outline" size={40} color={colors.outline} />
              <Text variant="bodyMedium" style={{ color: colors.outline }}>{t('noResults')}</Text>
              <Button mode="contained" onPress={wizard.requestNewCompany} icon="plus">
                {t('registerNew')}
              </Button>
            </View>
          ) : (
            <FlatList
              data={wizard.searchResults}
              keyExtractor={(item) => item.id}
              ItemSeparatorComponent={() => <Divider />}
              renderItem={({ item }) => (
                <Pressable
                  onPress={() => wizard.selectCompany(item)}
                  style={s.row}
                  android_ripple={{ color: colors.primaryContainer }}
                >
                  <MaterialCommunityIcons name="domain" size={22} color={colors.primary} />
                  <View style={{ flex: 1, marginLeft: 12 }}>
                    <Text variant="bodyMedium" style={{ fontWeight: '600' }}>{item.legal_name}</Text>
                    <Text variant="labelSmall" style={{ color: colors.outline }}>
                      {item.nif} · {item.zone_code || ''}
                    </Text>
                  </View>
                  <MaterialCommunityIcons name="chevron-right" size={20} color={colors.outline} />
                </Pressable>
              )}
            />
          )}
        </View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14 },
  registerNewBlock: { marginTop: 12, paddingBottom: 12 },
});
