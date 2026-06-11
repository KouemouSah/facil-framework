/**
 * Bundle Wizard — Dedicated screen for BUNDLE_PAYMENT workflow
 *
 * 5 steps: Company → Upload (optional) → Obligations → Payment → Confirmation
 * Completely separate from the generic wizard — aligned with web bundle-workflow module.
 */

import { useEffect, useRef } from 'react';
import { View, StyleSheet, Pressable, ScrollView } from 'react-native';
import { Text, Button, ActivityIndicator, ProgressBar, Snackbar, TextInput } from 'react-native-paper';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { MaterialCommunityIcons } from '@expo/vector-icons';

import { useAppTheme } from '@core/theme';
import {
  useBundleWizard,
  BundleStep,
  BUNDLE_STEP_LABELS,
  CompanyIdentificationStep,
  ObligationsReviewStep,
  BundlePaymentStep,
  BundleConfirmationStep,
} from '@modules/bundle-workflow';
import { CompanyUploadStep } from '@modules/bundle-workflow/components/company-upload';

export default function BundleWizardScreen() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { colors } = useAppTheme();
  const lang = (i18n.language || 'es') as string;
  // Deep-link parameters:
  //   • `company_id`  → "/bundle-wizard?company_id=…" lands the user with
  //                     their company pre-selected (used by the "Pagar
  //                     Obligaciones" CTA in /companies/[id]).
  //   • `mode=new`    → skip Step 0 (CompanyIdentification) and jump
  //                     directly to DOCUMENT_UPLOAD via
  //                     wizard.requestNewCompany(). Mirrors web
  //                     /dashboard/bundle-payment/[sessionId]?mode=new
  //                     (B5a parity 2026-04-29).
  const { company_id, mode } = useLocalSearchParams<{ company_id?: string; mode?: string }>();
  const wizard = useBundleWizard({ preselectCompanyId: company_id ?? null });

  // Apply `mode=new` exactly once on mount — same one-shot guard pattern
  // as web (autoSelectDone.current ref).
  const newModeAppliedRef = useRef(false);
  useEffect(() => {
    if (newModeAppliedRef.current) return;
    if (mode === 'new') {
      newModeAppliedRef.current = true;
      wizard.requestNewCompany();
    }
  }, [mode, wizard]);

  const stepLabel = BUNDLE_STEP_LABELS[wizard.currentStep as BundleStep]?.[lang] ||
    BUNDLE_STEP_LABELS[wizard.currentStep as BundleStep]?.es || '';
  const progress = (wizard.currentStep + 1) / wizard.totalSteps;

  return (
    <SafeAreaView style={[s.container, { backgroundColor: colors.background }]} edges={['top', 'bottom']}>
      {/* Header */}
      <View style={[s.header, { backgroundColor: colors.surface, borderBottomColor: colors.outlineVariant }]}>
        <Pressable onPress={() => (wizard.canGoBack ? wizard.goBack() : router.back())} style={{ padding: 4 }}>
          <MaterialCommunityIcons name={wizard.canGoBack ? 'arrow-left' : 'close'} size={24} color={colors.onSurface} />
        </Pressable>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text variant="titleMedium" style={{ fontWeight: '600' }}>
            {lang === 'fr' ? 'Paiement Obligations' : lang === 'en' ? 'Pay Obligations' : 'Pago Obligaciones'}
          </Text>
          <Text variant="labelSmall" style={{ color: colors.outline }}>
            {stepLabel} ({wizard.currentStep + 1}/{wizard.totalSteps})
          </Text>
        </View>
      </View>

      {/* Progress */}
      <ProgressBar progress={progress} color={colors.primary} style={{ height: 3 }} />

      {/* Step content */}
      <View style={{ flex: 1 }}>
        {wizard.isLoading ? (
          <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
            <ActivityIndicator size="large" color={colors.primary} />
          </View>
        ) : (
          <>
            {wizard.currentStep === BundleStep.COMPANY_IDENTIFICATION && (
              <CompanyIdentificationStep wizard={wizard} lang={lang} />
            )}
            {wizard.currentStep === BundleStep.DOCUMENT_UPLOAD && (
              <CompanyUploadStep wizard={wizard} lang={lang} />
            )}
            {wizard.currentStep === BundleStep.CLASSIFICATION && (
              <ScrollView contentContainerStyle={{ padding: 16, gap: 12, paddingBottom: 48 }}>
                {wizard.classificationPreview ? (
                  <>
                    {/* Editable company fields — full form review (aligned with web) */}
                    <TextInput label={lang === 'fr' ? 'Dénomination sociale *' : 'Nombre comercial *'} value={wizard.editedFields.legalName || ''} onChangeText={(v) => wizard.setEditedField('legalName', v || null)} mode="outlined" dense error={!wizard.editedFields.legalName} />
                    <TextInput label={lang === 'fr' ? 'N° Registre (PE-XXXX) *' : 'N° Registro (PE-XXXX) *'} value={wizard.editedFields.registrationNumber || ''} onChangeText={(v) => wizard.setEditedField('registrationNumber', v || null)} mode="outlined" dense placeholder={t('bundleWizard.registrationNumberPlaceholder')} error={!wizard.editedFields.registrationNumber} />
                    <TextInput label="NIF" value={wizard.editedFields.nif || ''} onChangeText={(v) => wizard.setEditedField('nif', v || null)} mode="outlined" dense autoCapitalize="characters" />
                    <TextInput label={lang === 'fr' ? 'Localité *' : 'Localidad *'} value={wizard.editedFields.localidad || ''} onChangeText={(v) => wizard.setEditedField('localidad', v || null)} mode="outlined" dense error={!wizard.editedFields.localidad} />
                    <TextInput label={lang === 'fr' ? 'Province' : 'Provincia'} value={wizard.editedFields.provincia || ''} onChangeText={(v) => wizard.setEditedField('provincia', v || null)} mode="outlined" dense />
                    <TextInput label={lang === 'fr' ? 'Forme juridique' : 'Forma jurídica'} value={wizard.editedFields.formaJuridica || ''} onChangeText={(v) => wizard.setEditedField('formaJuridica', v || null)} mode="outlined" dense />
                    <TextInput label={lang === 'fr' ? 'Secteur' : 'Sector'} value={wizard.editedFields.sector || ''} onChangeText={(v) => wizard.setEditedField('sector', v || null)} mode="outlined" dense />
                    <TextInput label={lang === 'fr' ? 'Objet social' : 'Objeto social'} value={wizard.editedFields.objetoSocial || ''} onChangeText={(v) => wizard.setEditedField('objetoSocial', v || null)} mode="outlined" dense multiline />

                    {/* Zone + Commerce type (auto-detected or manual) */}
                    <View style={{ gap: 4, marginTop: 8 }}>
                      <Text variant="labelMedium" style={{ fontWeight: '600' }}>{lang === 'fr' ? 'Zone fiscale' : 'Zona fiscal'}</Text>
                      <Text variant="bodyMedium" style={{ color: wizard.selectedZoneId ? colors.onSurface : colors.outline }}>
                        {wizard.classificationPreview.zone?.name || (lang === 'fr' ? 'Non détectée' : 'No detectada')}
                      </Text>
                    </View>
                    <View style={{ gap: 4 }}>
                      <Text variant="labelMedium" style={{ fontWeight: '600' }}>{lang === 'fr' ? 'Type de commerce' : 'Tipo de comercio'}</Text>
                      <Text variant="bodyMedium" style={{ color: wizard.selectedCommerceType ? colors.onSurface : colors.outline }}>
                        {wizard.selectedCommerceType || (lang === 'fr' ? 'Non classifié' : 'No clasificado')}
                      </Text>
                    </View>

                    {(!wizard.editedFields.registrationNumber || !wizard.editedFields.legalName || !wizard.editedFields.localidad) && (
                      <Text variant="labelSmall" style={{ color: colors.error }}>
                        {lang === 'fr' ? '* Les champs marqués sont obligatoires' : '* Los campos marcados son obligatorios'}
                      </Text>
                    )}
                  </>
                ) : (
                  <ActivityIndicator color={colors.primary} style={{ marginTop: 40 }} />
                )}
              </ScrollView>
            )}
            {wizard.currentStep === BundleStep.OBLIGATIONS_REVIEW && (
              <ObligationsReviewStep wizard={wizard} lang={lang} />
            )}
            {wizard.currentStep === BundleStep.PAYMENT && (
              <BundlePaymentStep wizard={wizard} lang={lang} />
            )}
            {wizard.currentStep === BundleStep.CONFIRMATION && (
              <BundleConfirmationStep wizard={wizard} lang={lang} />
            )}
          </>
        )}
      </View>

      {/* Navigation bar (hidden on confirmation) */}
      {wizard.currentStep < BundleStep.CONFIRMATION && (
        <View style={[s.navBar, { backgroundColor: colors.surface, borderTopColor: colors.outlineVariant }]}>
          {wizard.canGoBack ? (
            <Button mode="outlined" onPress={wizard.goBack} style={{ flex: 1, marginRight: 8 }}>
              {t('common.previous')}
            </Button>
          ) : <View style={{ flex: 1, marginRight: 8 }} />}
          <Button
            mode="contained"
            onPress={wizard.goNext}
            disabled={!wizard.canGoNext || wizard.isLoading}
            loading={wizard.isLoading || wizard.isPaymentProcessing}
            style={{ flex: 1 }}
          >
            {wizard.currentStep === BundleStep.PAYMENT
              ? (lang === 'fr' ? 'Payer' : lang === 'en' ? 'Pay' : 'Pagar')
              : t('common.next')}
          </Button>
        </View>
      )}

      {/* Error snackbar */}
      <Snackbar visible={!!wizard.error} onDismiss={wizard.clearError} duration={4000}
        action={{ label: 'OK', onPress: wizard.clearError }}>
        {wizard.error ?? ''}
      </Snackbar>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1 },
  navBar: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 12, paddingBottom: 16, borderTopWidth: 1 },
});
